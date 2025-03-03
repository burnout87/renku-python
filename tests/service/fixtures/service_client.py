#
# Copyright 2021 Swiss Data Science Center (SDSC)
# A partnership between École Polytechnique Fédérale de Lausanne (EPFL) and
# Eidgenössische Technische Hochschule Zürich (ETHZ).
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Renku service fixtures for client interactions."""
import os
import time
import urllib
import uuid
from pathlib import Path

import pytest

from renku.core.util.os import normalize_to_ascii


@pytest.fixture
def real_sync():
    """Enable remote sync."""
    import importlib

    from renku.core.util import git

    # NOTE: Use this fixture only in serial tests: git.push_changes is mocked; reloading the git module to undo the mock
    importlib.reload(git)


@pytest.fixture()
def svc_client(mock_redis, svc_cache_dir):
    """Renku service client."""
    from renku.ui.service.entrypoint import create_app

    flask_app = create_app()

    testing_client = flask_app.test_client()
    testing_client.testing = True

    ctx = flask_app.app_context()
    ctx.push()

    yield testing_client

    ctx.pop()


@pytest.fixture(scope="function")
def svc_cache_dir(mocker, tmpdir):
    """Mock temporary dir for cache."""
    import renku.ui.service.cache.models.file
    import renku.ui.service.cache.models.project
    import renku.ui.service.config
    import renku.ui.service.controllers.cache_files_delete_chunks
    import renku.ui.service.controllers.cache_files_upload
    import renku.ui.service.controllers.datasets_create
    import renku.ui.service.controllers.datasets_edit
    import renku.ui.service.entrypoint
    import renku.ui.service.utils

    project_dir = Path(tmpdir.mkdir("projects"))
    upload_dir = Path(tmpdir.mkdir("uploads"))

    mocker.patch.object(renku.ui.service.config, "CACHE_DIR", Path(tmpdir))
    mocker.patch.object(renku.ui.service.entrypoint, "CACHE_DIR", Path(tmpdir))
    mocker.patch.object(renku.ui.service.config, "CACHE_UPLOADS_PATH", upload_dir)
    mocker.patch.object(renku.ui.service.cache.models.project, "CACHE_PROJECTS_PATH", project_dir)
    mocker.patch.object(renku.ui.service.utils, "CACHE_PROJECTS_PATH", project_dir)
    mocker.patch.object(renku.ui.service.utils, "CACHE_UPLOADS_PATH", upload_dir)
    mocker.patch.object(renku.ui.service.cache.models.file, "CACHE_UPLOADS_PATH", upload_dir)
    mocker.patch.object(renku.ui.service.controllers.cache_files_upload, "CACHE_UPLOADS_PATH", upload_dir)
    mocker.patch.object(renku.ui.service.controllers.cache_files_delete_chunks, "CACHE_UPLOADS_PATH", upload_dir)
    mocker.patch.object(renku.ui.service.controllers.datasets_create, "CACHE_UPLOADS_PATH", upload_dir)
    mocker.patch.object(renku.ui.service.controllers.datasets_edit, "CACHE_UPLOADS_PATH", upload_dir)

    yield project_dir, upload_dir


@pytest.fixture(scope="function")
def svc_client_cache(mock_redis, identity_headers, svc_cache_dir):
    """Service jobs fixture."""
    from renku.ui.service.entrypoint import create_app

    flask_app = create_app()

    testing_client = flask_app.test_client()
    testing_client.testing = True

    ctx = flask_app.app_context()
    ctx.push()

    yield testing_client, identity_headers, flask_app.config.get("cache")

    ctx.pop()


@pytest.fixture(scope="module")
def identity_headers():
    """Get authentication headers."""
    import jwt

    from renku.ui.service.serializers.headers import JWT_TOKEN_SECRET

    jwt_data = {
        "jti": "12345",
        "exp": int(time.time()) + 1e6,
        "nbf": 0,
        "iat": 1595317694,
        "iss": "https://stable.dev.renku.ch/auth/realms/Renku",
        "aud": ["renku"],
        "sub": "9ab2fc80-3a5c-426d-ae78-56de01d214df",
        "typ": "ID",
        "azp": "renku",
        "nonce": "12345",
        "auth_time": 1595317694,
        "session_state": "12345",
        "acr": "1",
        "email_verified": False,
        "preferred_username": "renkubot@datascience.ch",
        "given_name": "Renku",
        "family_name": "Bot",
        "name": "Renkubot",
        "email": "renkubot@datascience.ch",
    }

    headers = {
        "Content-Type": "application/json",
        "Renku-User": jwt.encode(jwt_data, JWT_TOKEN_SECRET, algorithm="HS256"),
        "Authorization": "Bearer {}".format(os.getenv("IT_OAUTH_GIT_TOKEN")),
    }

    return headers


@pytest.fixture(scope="module")
def view_user_data(identity_headers):
    """View user data object."""
    from renku.ui.service.serializers.headers import RequiredIdentityHeaders

    user_data = RequiredIdentityHeaders().load(identity_headers)

    return user_data


@pytest.fixture
def svc_client_with_user(svc_client_cache):
    """Service client with a predefined user."""
    from werkzeug.utils import secure_filename

    from renku.ui.service.serializers.headers import encode_b64

    svc_client, headers, cache = svc_client_cache

    user_id = encode_b64(secure_filename("9ab2fc80-3a5c-426d-ae78-56de01d214df"))
    user = cache.ensure_user({"user_id": user_id})

    yield svc_client, headers, cache, user


@pytest.fixture
def svc_synced_client(svc_client_with_user, real_sync):
    """Renku service client with remote sync."""
    yield svc_client_with_user


@pytest.fixture
def svc_client_with_templates(svc_client, mock_redis, identity_headers, template):
    """Setup and teardown steps for templates tests."""

    yield svc_client, identity_headers, template


@pytest.fixture
def svc_client_templates_creation(svc_client_with_templates):
    """Setup and teardown steps for templates tests."""
    from renku.core.util import requests

    svc_client, authentication_headers, template = svc_client_with_templates
    parameters = []
    for parameter in template["metadata"].keys():
        parameters.append({"key": parameter, "value": template["metadata"][parameter]})

    payload = {
        **template,
        "identifier": template["id"],
        "parameters": parameters,
        "project_name": f"Test renku-core {uuid.uuid4().hex[:12]}",
        "project_namespace": "renku-python-integration-tests",
        "project_repository": "https://gitlab.dev.renku.ch",
        "project_description": "new service project",
        "project_custom_metadata": {
            "@id": "http://example.com/metadata12",
            "@type": "https://schema.org/myType",
            "https://schema.org/property1": 1,
            "https://schema.org/property2": "test",
        },
    }

    # cleanup by invoking the GitLab delete API
    # TODO: consider using the project delete endpoint once implemented
    def remove_project():
        project_slug = "{}/{}".format(payload["project_namespace"], normalize_to_ascii(payload["project_name"]))

        project_slug_encoded = urllib.parse.quote(project_slug, safe="")
        project_delete_url = "{}/api/v4/projects/{}".format(payload["project_repository"], project_slug_encoded)

        requests.delete(url=project_delete_url, headers=authentication_headers)

        return True

    yield svc_client, authentication_headers, payload, remove_project

    remove_project()
