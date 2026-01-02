from src.exceptions import StorageSSLError, StorageResponseError, StorageConnectionError, \
    StorageNotFound, StorageGone, StorageConflict

from pathlib import Path
import requests


class SecretsStorageClient:
    def __init__(
        self,
        base_url: str,
        cert: tuple[str, str],
        ca: str,
        timeout: int = 10,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

        self.session = requests.Session()
        self.session.cert = cert
        self.session.verify = ca
        self.session.proxies = {"http": None, "https": None}

    def _request(
            self,
            method: str,
            path: str,
            *,
            json: dict | None = None,
            files: dict | None = None,
            data: dict | None = None,
            stream: bool = False,
            expected_status: tuple[int, ...],
    ) -> requests.Response:

        try:
            response = self.session.request(
                method=method,
                url=f"{self.base_url}{path}",
                json=json,
                files=files,
                data=data,
                stream=stream,
                timeout=self.timeout,
                cert=self.session.cert,
                verify=self.session.verify,
                proxies=self.session.proxies
            )

        except requests.exceptions.SSLError as e:
            raise StorageSSLError(
                "Ошибка mTLS: неверный клиентский сертификат или CA"
            ) from e
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
            raise StorageConnectionError("Storage недоступен") from e

        if response.status_code not in expected_status:
            if response.status_code == 404:
                raise StorageNotFound()
            if response.status_code == 409:
                raise StorageConflict()
            if response.status_code == 410:
                raise StorageGone()
            raise StorageResponseError(response.status_code, response.text)

        return response


    def health(self) -> None:
        self._request(
            "GET",
            "/health",
            expected_status=(200,),
        )


    def get_secret_string(self, name: str, version: int | None = None) -> dict:
        params = f"?version={version}" if version is not None else ""

        response = self._request(
            "GET",
            f"/secret_string/{name}{params}",
            expected_status=(200, ),
        )

        return response.json()


    def create_secret_string(
        self,
        name: str,
        encrypted_data: str,
        nonce: str,
        sha256: str,
    ) -> None:
        self._request(
            "POST",
            "/secrets_strings/create_string",
            json={
                "name": name,
                "encrypted_data": encrypted_data,
                "nonce": nonce,
                "sha256": sha256,
            },
            expected_status=(201,),
        )


    def create_next_string_version(
        self,
        name: str,
        encrypted_data: str,
        nonce: str,
        sha256: str,
    ) -> None:
        self._request(
            "POST",
            "/secrets_strings/versions",
            json={
                "name": name,
                "encrypted_data": encrypted_data,
                "nonce": nonce,
                "sha256": sha256,
            },
            expected_status=(201,),
        )


    def get_secret_file_meta(self, name: str, version: int | None = None) -> dict:
        params = f"?version={version}" if version is not None else ""

        response = self._request(
            "GET",
            f"/secrets/files/{name}{params}",
            expected_status=(200, 404),
        )

        return response.json()


    def upload_secret_file(
        self,
        name: str,
        file_path: Path,
        nonce_b64: str,
        sha256_b64: str,
    ) -> None:
        with file_path.open("rb") as f:
            self._request(
                "POST",
                "/secrets_files/create_files",
                files={"file": f},
                data={
                    "name": name,
                    "nonce": nonce_b64,
                    "sha256": sha256_b64,
                },
                expected_status=(201,),
            )


    def upload_next_file_version(
        self,
        name: str,
        file_path: Path,
        nonce_b64: str,
        sha256_b64: str,
    ) -> None:
        with file_path.open("rb") as f:
            self._request(
                "POST",
                "/secrets_files/versions",
                files={"file": f},
                data={
                    "name": name,
                    "nonce": nonce_b64,
                    "sha256": sha256_b64,
                },
                expected_status=(201,),
            )


    def download_secret_file(
        self,
        name: str,
        dst_path: Path,
        version: int | None = None,
    ) -> None:
        params = f"?version={version}" if version is not None else ""

        response = self._request(
            "GET",
            f"/secrets/files/{name}/download{params}",
            stream=True,
            expected_status=(200,),
        )

        with dst_path.open("wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)

    def purge_secret(
        self,
        name: str
    ) -> None:
        self._request(
            "DELETE",
            f"/secrets/{name}/purge",
            stream=True,
            expected_status=(202,),
        )