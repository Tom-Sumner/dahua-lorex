import aiohttp
import json
import hashlib
import logging
import sys
from dataclasses import dataclass
from typing import Any

_LOGGER: logging.Logger = logging.getLogger(__package__)

if sys.version_info > (3, 0):
    unicode = str


@dataclass(unsafe_hash=True)
class CoaxialControlIOStatus:
    speaker: bool = False
    white_light: bool = False
    api_response: Any = None

    def __post_init__(self):
        if self.api_response is not None:
            self.speaker = self.api_response["params"]["status"]["Speaker"] == "On"
            self.white_light = self.api_response["params"]["status"]["WhiteLight"] == "On"


class DahuaRpc2Client:
    def __init__(
            self,
            username: str,
            password: str,
            address: str,
            port: int,
            rtsp_port: int,
            session: aiohttp.ClientSession
    ) -> None:
        self._username = username
        self._password = password
        self._session = session
        self._rtsp_port = rtsp_port
        self._session_id = None
        self._id = 0
        protocol = "https" if port == 443 else "http"
        self._base = f"{protocol}://{address}:{port}"
        self.logged_in = False
        _LOGGER.debug(f"DahuaRpc2Client initialized with base URL: {self._base}")

    async def request(self, method, params=None, object_id=None, extra=None, url=None, verify_result=True):
        """Make an RPC request."""
        self._id += 1
        data = {'method': method, 'id': self._id}
        if params is not None:
            data['params'] = params
        if object_id:
            data['object'] = object_id
        if extra is not None:
            data.update(extra)
        if self._session_id:
            data['session'] = self._session_id
        if not url:
            url = f"{self._base}/RPC2"

        _LOGGER.debug(f"Requesting {method} with params {params} to URL: {url} Using session: {self._session_id}")

        try:
            async with self._session.post(url, data=json.dumps(data)) as resp:
                text_response = await resp.text()
                _LOGGER.debug(f"Response Text: {text_response}")

                try:
                    resp_json = json.loads(text_response)
                except json.JSONDecodeError:
                    _LOGGER.error(f"Failed to decode JSON. Response text: {text_response}")
                    raise ValueError("Failed to decode JSON response")

                if verify_result and resp_json.get('result') is False:
                    _LOGGER.error(f"API call failed: {resp_json}")
                    raise ConnectionError(f"API call failed: {resp_json}")

                return resp_json
        except Exception as e:
            _LOGGER.error(f"Request failed: {e}")
            raise

    async def login(self):
        """Dahua RPC login."""
        _LOGGER.debug("Attempting to log in")
        self._session_id = None
        self._id = 0
        url = '{0}/RPC2_Login'.format(self._base)
        method = "global.login"
        params = {'userName': self._username,
                  'password': "",
                  'clientType': "Dahua3.0-Web3.0"}

        r = await self.request(method=method, params=params, url=url, verify_result=False)
        _LOGGER.debug(f"Initial login response: {r}")

        self._session_id = r['session']
        realm = r['params']['realm']
        random = r['params']['random']

        _LOGGER.debug(f"Received session: {self._session_id}, realm: {realm}, random: {random}")

        # Password encryption algorithm
        pwd_phrase = f"{self._username}:{realm}:{self._password}"
        pwd_hash = hashlib.md5(pwd_phrase.encode('utf-8')).hexdigest().upper()
        pass_phrase = f"{self._username}:{random}:{pwd_hash}"
        pass_hash = hashlib.md5(pass_phrase.encode('utf-8')).hexdigest().upper()

        _LOGGER.debug(f"Password hash: {pass_hash}")

        params = {'userName': self._username,
                  'password': pass_hash,
                  'clientType': "Dahua3.0-Web3.0",
                  'authorityType': "Default",
                  'passwordType': "Default"}

        response = await self.request(method=method, params=params, url=url)
        _LOGGER.debug(f"Final login response: {response}")

        if response.get("result") == True:
            self.logged_in = True
            self._session
            _LOGGER.info(f"Login successful. Device Time: {await self.current_time()}")
            return response
        else:
            _LOGGER.error("Login failed")
            return False

    async def logout(self) -> bool:
        """Logs out of the current session."""
        _LOGGER.debug("Attempting to log out")
        try:
            response = await self.request(method="global.logout")
            _LOGGER.debug(f"Logout response: {response}")
            if response.get('result') is True:
                _LOGGER.info("Logout successful")
                return True
            else:
                _LOGGER.debug("Failed to log out")
                return False
        except Exception as e:
            _LOGGER.error(f"Logout failed: {e}")
            return False

    async def current_time(self):
        """Get the current time on the device."""
        _LOGGER.debug("Fetching current time")
        response = await self.request(method="global.getCurrentTime")
        _LOGGER.debug(f"Current time response: {response}")
        return response['params']['time']

    async def get_serial_number(self) -> str:
        """Gets the serial number of the device."""
        _LOGGER.debug("Fetching serial number")
        response = await self.request(method="magicBox.getSerialNo")
        _LOGGER.debug(f"Serial number response: {response}")
        return response['params']['sn']

    async def get_config(self, params):
        """Gets config for the supplied params."""
        _LOGGER.debug(f"Fetching config with params: {params}")
        response = await self.request(method="configManager.getConfig", params=params)
        _LOGGER.debug(f"Config response: {response}")
        return response['params']

    async def get_device_name(self) -> str:
        """Get the device name."""
        _LOGGER.debug("Fetching device name")
        data = await self.get_config({"name": "General"})
        _LOGGER.debug(f"Device name config: {data}")
        return data["table"]["MachineName"]

    async def get_coaxial_control_io_status(self, channel: int) -> CoaxialControlIOStatus:
        """Returns the current state of the speaker and white light."""
        await self.login()
        _LOGGER.debug(f"Fetching coaxial control IO status for channel: {channel}")
        response = await self.request(method="CoaxialControlIO.getStatus", params={"channel": channel})
        _LOGGER.debug(f"Coaxial control IO status response: {response}")
        return CoaxialControlIOStatus(api_response=response)


    async def set_coaxial_control_io_status(self, channel: int, type: int, io: int, trigger_mode: int) -> CoaxialControlIOStatus:
        """Controls the current state of the speaker and white light."""
        await self.login()
        _LOGGER.debug(f"Setting coaxial control IO status for channel: {channel}, type: {type}, io: {io}, trigger_mode: {trigger_mode}")
        await self.request(method="CoaxialControlIO.control", params={"channel": channel, "info": [{"Type": type, "IO": io, "TriggerMode": trigger_mode}]})
        _LOGGER.debug("Coaxial control IO status set, fetching updated status")
        return await self.get_coaxial_control_io_status(channel)
