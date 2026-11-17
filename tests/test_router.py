from unittest.mock import MagicMock, patch

from fritzconnection.core.exceptions import (
    FritzActionError, FritzAuthorizationError, FritzConnectionException,
    FritzLookUpError, FritzSecurityError,
)
from fritzconnection.core.soaper import raise_fritzconnection_error
from requests import Response
from requests.exceptions import ConnectionError, HTTPError, RequestException, Timeout

from telegram_fritz_wol.router import FritzRouter, Reachability, RouterError

from .common import DEVICES, OfflineTestCase, settings


def soap_fault_response(code, description):
    response = Response()
    response.status_code = 500
    response.headers["Content-Type"] = "text/xml; charset=utf-8"
    response._content = f'''<?xml version="1.0"?>
<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/">
  <s:Body><s:Fault>
    <faultcode>s:Client</faultcode><faultstring>UPnPError</faultstring>
    <detail><UPnPError xmlns="urn:schemas-upnp-org:control-1-0">
      <errorCode>{code}</errorCode>
      <errorDescription>{description}</errorDescription>
    </UPnPError></detail>
  </s:Fault></s:Body>
</s:Envelope>'''.encode("utf-8")
    return response


class RouterTests(OfflineTestCase):
    def setUp(self):
        super().setUp()
        factory = patch("telegram_fritz_wol.router.FritzConnection", autospec=True)
        self.factory = factory.start()
        self.addCleanup(factory.stop)
        self.connection = self.factory.return_value
        # session is created by FritzConnection.__init__, so class autospec
        # cannot discover it without constructing the real network client.
        self.connection.session = MagicMock()
        self.router = FritzRouter(settings())

    def test_lazy_creation_authenticated_wol_and_reuse(self):
        self.factory.assert_not_called()
        self.router.wake(DEVICES[0].mac)
        self.router.wake(DEVICES[1].mac)
        self.factory.assert_called_once_with(address="192.168.178.1", user="test-user",
                                             password="test-password", timeout=5,
                                             use_tls=False, use_cache=False, redact_debug_log=True)
        self.connection.call_action.assert_any_call("Hosts1", "X_AVM-DE_WakeOnLANByMACAddress", NewMACAddress=DEVICES[0].mac)
        self.assertEqual(self.connection.call_action.call_count, 2)

    def test_status_action_and_bool_parsing(self):
        for value, expected in (
            (True, Reachability.ACTIVE), (1, Reachability.ACTIVE), ("1", Reachability.ACTIVE),
            ("true", Reachability.ACTIVE), (False, Reachability.INACTIVE),
            (0, Reachability.INACTIVE), ("0", Reachability.INACTIVE), ("false", Reachability.INACTIVE),
            (None, Reachability.UNKNOWN), ("unexpected", Reachability.UNKNOWN), (2, Reachability.UNKNOWN),
        ):
            self.connection.call_action.return_value = {"NewActive": value}
            with self.subTest(value=value):
                self.assertEqual(self.router.status(DEVICES[0].mac), expected)
        self.connection.call_action.assert_called_with("Hosts1", "GetSpecificHostEntry", NewMACAddress=DEVICES[0].mac)

    def test_missing_host_is_unknown_not_offline(self):
        self.connection.call_action.side_effect = FritzLookUpError("sensitive")
        self.assertEqual(self.router.status(DEVICES[0].mac), Reachability.UNKNOWN)

    def test_soap_fault_714_is_lookup_error_and_status_unknown(self):
        response = soap_fault_response(714, "NoSuchEntryInArray")
        # Exercise the installed library's parser, rather than assuming its
        # exception mapping. In 1.15.1, 714 is FritzLookUpError, which also
        # inherits from FritzConnectionException and KeyError.
        with self.assertRaises(FritzLookUpError) as caught:
            raise_fritzconnection_error(response)
        self.assertIs(type(caught.exception), FritzLookUpError)

        self.connection.call_action.side_effect = lambda *args, **kwargs: raise_fritzconnection_error(response)
        self.assertEqual(self.router.status(DEVICES[0].mac), Reachability.UNKNOWN)
        self.connection.call_action.assert_called_once_with(
            "Hosts1", "GetSpecificHostEntry", NewMACAddress=DEVICES[0].mac,
        )

    def test_other_soap_faults_remain_errors_during_status(self):
        for code, expected in ((401, "router"), (501, "router"),
                               (606, "authentication"), (999, "router")):
            with self.subTest(code=code):
                response = soap_fault_response(code, "sensitive-secret")
                self.connection.call_action.reset_mock()
                self.connection.call_action.side_effect = lambda *args, **kwargs: raise_fritzconnection_error(response)
                with self.assertRaises(RouterError) as caught:
                    self.router.status(DEVICES[0].mac)
                self.assertEqual(caught.exception.category, expected)
                self.assertNotIn("sensitive-secret", str(caught.exception))
                self.connection.call_action.assert_called_once_with(
                    "Hosts1", "GetSpecificHostEntry", NewMACAddress=DEVICES[0].mac,
                )

    def test_soap_fault_714_during_wol_remains_a_safe_error(self):
        response = soap_fault_response(714, "sensitive-secret")
        self.connection.call_action.side_effect = lambda *args, **kwargs: raise_fritzconnection_error(response)
        with self.assertRaises(RouterError) as caught:
            self.router.wake(DEVICES[0].mac)
        self.assertEqual(caught.exception.category, "unknown_host")
        self.assertNotIn("sensitive-secret", str(caught.exception))
        self.connection.call_action.assert_called_once_with(
            "Hosts1", "X_AVM-DE_WakeOnLANByMACAddress", NewMACAddress=DEVICES[0].mac,
        )

    def test_errors_are_classified_redacted_and_never_retried(self):
        for exception, expected in (
            (FritzAuthorizationError, "authentication"), (FritzSecurityError, "authentication"),
            (Timeout, "timeout"), (ConnectionError, "connection"),
            (FritzConnectionException, "router"), (FritzActionError, "router"),
            (RequestException, "router"), (FritzLookUpError, "unknown_host"),
        ):
            self.connection.call_action.reset_mock()
            self.connection.call_action.side_effect = exception("sensitive-secret")
            with self.subTest(exception=exception), self.assertRaises(RouterError) as caught:
                self.router.wake(DEVICES[0].mac)
            self.assertEqual(caught.exception.category, expected)
            self.assertNotIn("sensitive-secret", str(caught.exception))
            self.connection.call_action.assert_called_once()

    def test_http_auth_errors(self):
        for status in (401, 403, 500):
            response = Response()
            response.status_code = status
            self.connection.call_action.side_effect = HTTPError("sensitive", response=response)
            with self.subTest(status=status), self.assertRaises(RouterError) as caught:
                self.router.wake(DEVICES[0].mac)
            self.assertEqual(caught.exception.category, "authentication" if status in (401, 403) else "router")

    def test_initial_discovery_failure_does_not_send_wol(self):
        self.factory.side_effect = Timeout("sensitive")
        with self.assertRaises(RouterError):
            self.router.wake(DEVICES[0].mac)
        self.connection.call_action.assert_not_called()
        self.factory.assert_called_once()

    def test_close_releases_session(self):
        self.router.close()
        self.factory.assert_not_called()
        self.router.wake(DEVICES[0].mac)
        self.router.close()
        self.connection.session.close.assert_called_once()
        self.router.close()
        self.connection.session.close.assert_called_once()
