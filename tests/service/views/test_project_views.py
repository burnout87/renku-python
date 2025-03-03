#
# Copyright 2019-2023 - Swiss Data Science Center (SDSC)
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
"""Renku service project view tests."""
import json
import time

import portalocker
import pytest

from renku.ui.service.errors import ProgramInvalidGenericFieldsError
from tests.service.views.test_dataset_views import assert_rpc_response
from tests.utils import retry_failed


@pytest.mark.service
@pytest.mark.integration
@retry_failed
def test_show_project_view(svc_client_with_repo):
    """Test show project metadata."""
    svc_client, headers, project_id, url_components = svc_client_with_repo

    show_payload = {
        "git_url": url_components.href,
    }
    response = svc_client.post("/project.show", data=json.dumps(show_payload), headers=headers)

    assert_rpc_response(response)
    assert {
        "id",
        "name",
        "description",
        "created",
        "creator",
        "agent",
        "custom_metadata",
        "template_info",
        "keywords",
    } == set(response.json["result"])


@pytest.mark.service
@pytest.mark.integration
@pytest.mark.parametrize(
    "custom_metadata",
    [
        [
            {
                "@id": "http://example.com/metadata12",
                "@type": "https://schema.org/myType",
                "https://schema.org/property1": 1,
                "https://schema.org/property2": "test",
            },
        ],
        [
            {
                "@id": "http://example.com/metadata12",
                "@type": "https://schema.org/myType",
                "https://schema.org/property1": 1,
                "https://schema.org/property2": "test",
            },
            {
                "@id": "http://example.com/metadata1",
                "@type": "https://schema.org/myType1",
                "https://schema.org/property4": 3,
                "https://schema.org/property5": "test1",
            },
        ],
    ],
)
@pytest.mark.parametrize("custom_metadata_source", [None, "testSource"])
@retry_failed
def test_edit_project_view(svc_client_with_repo, custom_metadata, custom_metadata_source):
    """Test editing project metadata."""
    svc_client, headers, project_id, url_components = svc_client_with_repo

    edit_payload = {
        "git_url": url_components.href,
        "description": "my new title",
        "creator": {"name": "name123", "email": "name123@ethz.ch", "affiliation": "ethz"},
        "custom_metadata": custom_metadata,
    }
    if custom_metadata_source is not None:
        edit_payload["custom_metadata_source"] = custom_metadata_source
    response = svc_client.post("/project.edit", data=json.dumps(edit_payload), headers=headers)

    assert_rpc_response(response)
    assert {"warning", "edited", "remote_branch"} == set(response.json["result"])
    assert {
        "description": "my new title",
        "creator": {"name": "name123", "email": "name123@ethz.ch", "affiliation": "ethz"},
        "custom_metadata": custom_metadata,
    } == response.json["result"]["edited"]

    edit_payload = {
        "git_url": url_components.href,
    }
    response = svc_client.post("/project.edit", data=json.dumps(edit_payload), headers=headers)

    assert_rpc_response(response)
    assert {"warning", "edited", "remote_branch"} == set(response.json["result"])
    assert 0 == len(response.json["result"]["edited"])


@pytest.mark.service
@pytest.mark.integration
@retry_failed
def test_edit_project_view_unset(svc_client_with_repo):
    """Test editing project metadata by unsetting values."""
    svc_client, headers, project_id, url_components = svc_client_with_repo

    edit_payload = {
        "git_url": url_components.href,
        "description": "my new title",
        "creator": {"name": "name123", "email": "name123@ethz.ch", "affiliation": "ethz"},
        "keywords": ["keyword1", "keyword2"],
        "custom_metadata": [
            {
                "@id": "http://example.com/metadata12",
                "@type": "https://schema.org/myType",
                "https://schema.org/property1": 1,
                "https://schema.org/property2": "test",
            }
        ],
    }
    response = svc_client.post("/project.edit", data=json.dumps(edit_payload), headers=headers)

    edit_payload = {"git_url": url_components.href, "custom_metadata": None, "keywords": None}
    response = svc_client.post("/project.edit", data=json.dumps(edit_payload), headers=headers)

    assert_rpc_response(response)
    assert {"warning", "edited", "remote_branch"} == set(response.json["result"])
    assert {
        "keywords": None,
        "custom_metadata": None,
    } == response.json[
        "result"
    ]["edited"]


@pytest.mark.service
@pytest.mark.integration
@retry_failed
def test_edit_project_view_failures(svc_client_with_repo):
    """Test failures when editing project metadata providing wrong data."""
    svc_client, headers, project_id, url_components = svc_client_with_repo

    payload = {
        "git_url": url_components.href,
        "description": "my new title",
        "creator": {"name": "name123", "email": "name123@ethz.ch", "affiliation": "ethz"},
        "custom_metadata": [
            {
                "@id": "http://example.com/metadata12",
                "@type": "https://schema.org/myType",
                "https://schema.org/property1": 1,
                "https://schema.org/property2": "test",
            }
        ],
    }
    payload["FAKE_FIELD"] = "FAKE_VALUE"
    response = svc_client.post("/project.edit", data=json.dumps(payload), headers=headers)

    assert_rpc_response(response, "error")
    assert ProgramInvalidGenericFieldsError.code == response.json["error"]["code"]


@pytest.mark.integration
@pytest.mark.service
@retry_failed
def test_remote_edit_view(svc_client, it_remote_repo_url, identity_headers):
    """Test creating a delayed edit."""
    response = svc_client.post(
        "/project.edit",
        data=json.dumps(dict(git_url=it_remote_repo_url, is_delayed=True)),
        headers=identity_headers,
    )

    assert_rpc_response(response)
    assert response.json["result"]["created_at"]
    assert response.json["result"]["job_id"]


@pytest.mark.integration
@pytest.mark.service
def test_get_lock_status_unlocked(svc_client_setup):
    """Test getting lock status for an unlocked project."""
    svc_client, headers, project_id, url_components, _ = svc_client_setup

    response = svc_client.get(
        "/1.1/project.lock_status",
        query_string={"git_url": url_components.href, "timeout": 1.0},
        headers=headers,
        content_type="text/xml",
    )

    assert_rpc_response(response)
    assert {"locked"} == set(response.json["result"].keys())
    assert response.json["result"]["locked"] is False


@pytest.mark.integration
@pytest.mark.service
def test_get_lock_status_locked(svc_client_setup):
    """Test getting lock status for a locked project."""
    svc_client, headers, project_id, url_components, repository = svc_client_setup

    def mock_lock():
        return portalocker.Lock(f"{repository.path}.lock", flags=portalocker.LOCK_EX, timeout=0)

    with mock_lock():
        start = time.monotonic()
        response = svc_client.get(
            "/1.1/project.lock_status", query_string={"git_url": url_components.href, "timeout": 1.0}, headers=headers
        )
        assert time.monotonic() - start >= 1.0

    assert_rpc_response(response)
    assert {"locked"} == set(response.json["result"].keys())
    assert response.json["result"]["locked"] is True


@pytest.mark.integration
@pytest.mark.service
def test_get_lock_status_for_project_not_in_cache(svc_client, identity_headers):
    """Test getting lock status for an unlocked project which is not cached."""
    response = svc_client.get(
        "/1.1/project.lock_status", query_string={"git_url": "https://example.com/repo.git"}, headers=identity_headers
    )

    assert_rpc_response(response)
    assert {"locked"} == set(response.json["result"].keys())
    assert response.json["result"]["locked"] is False
