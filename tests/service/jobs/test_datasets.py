#
# Copyright 2020-2023 - Swiss Data Science Center (SDSC)
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
"""Renku service dataset jobs tests."""
import json
import tempfile
import uuid

import jwt
import pytest
from werkzeug.utils import secure_filename

from renku.core.errors import DatasetExistsError, DatasetNotFound, ParameterError
from renku.infrastructure.repository import Repository
from renku.ui.service.jobs.datasets import dataset_add_remote_file, dataset_import
from renku.ui.service.serializers.headers import JWT_TOKEN_SECRET, encode_b64
from renku.ui.service.utils import make_project_path
from tests.utils import assert_rpc_response, retry_failed


@pytest.mark.parametrize("url", ["https://dev.renku.ch/datasets/428c36261c56463d8753336470cc6917/"])
@pytest.mark.integration
@pytest.mark.service
@retry_failed
@pytest.mark.vcr
def test_dataset_url_import_job(url, svc_client_with_repo):
    """Test dataset import via url."""
    svc_client, headers, project_id, url_components = svc_client_with_repo

    decoded = jwt.decode(headers["Renku-User"], JWT_TOKEN_SECRET, algorithms=["HS256"], audience="renku")
    user_data = {
        "fullname": decoded["name"],
        "email": decoded["email"],
        "user_id": encode_b64(secure_filename(decoded["sub"])),
        "token": headers["Authorization"].split("Bearer ")[-1],
    }

    payload = {
        "git_url": url_components.href,
        "dataset_uri": url,
    }

    response = svc_client.post("/datasets.import", data=json.dumps(payload), headers=headers)

    assert_rpc_response(response)
    assert {"job_id", "created_at"} == set(response.json["result"].keys())

    dest = make_project_path(
        user_data,
        {
            "owner": url_components.owner,
            "name": url_components.name,
            "slug": url_components.slug,
            "project_id": project_id,
        },
    )

    old_commit = Repository(dest).head.commit
    job_id = response.json["result"]["job_id"]

    commit_message = "service: import remote dataset"
    dataset_import(user_data, job_id, project_id, url, commit_message=commit_message)

    new_commit = Repository(dest).head.commit
    assert old_commit.hexsha != new_commit.hexsha
    assert commit_message.splitlines()[0] == new_commit.message.splitlines()[0]

    response = svc_client.get(f"/jobs/{job_id}", headers=headers)

    assert_rpc_response(response)
    assert "COMPLETED" == response.json["result"]["state"]


@pytest.mark.parametrize("doi", ["10.5281/zenodo.3239980", "10.5281/zenodo.3188334", "10.7910/DVN/TJCLKP"])
@pytest.mark.integration
@pytest.mark.service
@retry_failed
@pytest.mark.vcr
def test_dataset_import_job(doi, svc_client_with_repo):
    """Test dataset import via doi."""
    svc_client, headers, project_id, url_components = svc_client_with_repo

    user_id = encode_b64(secure_filename("9ab2fc80-3a5c-426d-ae78-56de01d214df"))
    user = {"user_id": user_id}

    payload = {
        "git_url": url_components.href,
        "dataset_uri": doi,
    }
    response = svc_client.post("/datasets.import", data=json.dumps(payload), headers=headers)

    assert_rpc_response(response)
    assert {"job_id", "created_at"} == set(response.json["result"].keys())

    dest = make_project_path(
        user,
        {
            "owner": url_components.owner,
            "name": url_components.name,
            "slug": url_components.slug,
            "project_id": project_id,
        },
    )

    old_commit = Repository(dest).head.commit
    job_id = response.json["result"]["job_id"]

    commit_message = "service: import remote dataset"
    dataset_import(user, job_id, project_id, doi, commit_message=commit_message)

    new_commit = Repository(dest).head.commit
    assert old_commit.hexsha != new_commit.hexsha
    assert commit_message.splitlines()[0] == new_commit.message.splitlines()[0]

    response = svc_client.get(f"/jobs/{job_id}", headers=headers)

    assert_rpc_response(response)
    assert "COMPLETED" == response.json["result"]["state"]


@pytest.mark.parametrize(
    "doi,expected_err",
    [
        # not valid doi
        ("junkjunkjunk", "Invalid parameter value"),
        # not existing doi
        ("10.5281/zenodo.11111111111111111", "Invalid parameter value"),
    ],
)
@pytest.mark.integration
@pytest.mark.service
@retry_failed
@pytest.mark.vcr
def test_dataset_import_junk_job(doi, expected_err, svc_client_with_repo):
    """Test dataset import."""
    svc_client, headers, project_id, url_components = svc_client_with_repo

    user_id = encode_b64(secure_filename("9ab2fc80-3a5c-426d-ae78-56de01d214df"))
    user = {"user_id": user_id}

    payload = {
        "git_url": url_components.href,
        "dataset_uri": doi,
    }
    response = svc_client.post("/datasets.import", data=json.dumps(payload), headers=headers)

    assert_rpc_response(response)
    assert {"job_id", "created_at"} == set(response.json["result"].keys())

    dest = make_project_path(
        user,
        {
            "owner": url_components.owner,
            "name": url_components.name,
            "slug": url_components.slug,
            "project_id": project_id,
        },
    )

    old_commit = Repository(dest).head.commit
    job_id = response.json["result"]["job_id"]

    with pytest.raises(ParameterError):
        dataset_import(user, job_id, project_id, doi)

    new_commit = Repository(dest).head.commit
    assert old_commit.hexsha == new_commit.hexsha

    response = svc_client.get(f"/jobs/{job_id}", data=json.dumps(payload), headers=headers)

    assert_rpc_response(response)
    extras = response.json["result"]["extras"]

    assert "error" in extras
    assert expected_err in extras["error"]


@pytest.mark.parametrize("doi", ["10.5281/zenodo.3634052"])
@pytest.mark.integration
@pytest.mark.service
@retry_failed
@pytest.mark.vcr
def test_dataset_import_twice_job(doi, svc_client_with_repo):
    """Test dataset import."""
    svc_client, headers, project_id, url_components = svc_client_with_repo

    user_id = encode_b64(secure_filename("9ab2fc80-3a5c-426d-ae78-56de01d214df"))
    user = {"user_id": user_id}

    payload = {
        "git_url": url_components.href,
        "dataset_uri": doi,
    }
    response = svc_client.post("/datasets.import", data=json.dumps(payload), headers=headers)

    assert_rpc_response(response)
    assert {"job_id", "created_at"} == set(response.json["result"].keys())

    dest = make_project_path(
        user,
        {
            "owner": url_components.owner,
            "name": url_components.name,
            "slug": url_components.slug,
            "project_id": project_id,
        },
    )

    old_commit = Repository(dest).head.commit
    job_id = response.json["result"]["job_id"]

    dataset_import(user, job_id, project_id, doi)

    new_commit = Repository(dest).head.commit
    assert old_commit.hexsha != new_commit.hexsha

    with pytest.raises(DatasetExistsError):
        dataset_import(user, job_id, project_id, doi)

    new_commit2 = Repository(dest).head.commit
    assert new_commit.hexsha == new_commit2.hexsha

    response = svc_client.get(f"/jobs/{job_id}", data=json.dumps(payload), headers=headers)

    assert_rpc_response(response)
    extras = response.json["result"]["extras"]

    assert "error" in extras
    assert "Dataset exists" in extras["error"]


@pytest.mark.parametrize(
    "url", ["https://gist.github.com/jsam/d957f306ed0fe4ff018e902df6a1c8e3", "https://tinyurl.com/y6gne4ct"]
)
@pytest.mark.integration
@pytest.mark.service
@retry_failed
@pytest.mark.vcr
def test_dataset_add_remote_file(url, svc_client_with_repo):
    """Test dataset add a remote file."""
    svc_client, headers, project_id, url_components = svc_client_with_repo

    user_id = encode_b64(secure_filename("9ab2fc80-3a5c-426d-ae78-56de01d214df"))
    user = {"user_id": user_id}

    payload = {
        "git_url": url_components.href,
        "name": uuid.uuid4().hex,
        "create_dataset": True,
        "files": [{"file_url": url}],
    }
    response = svc_client.post("/datasets.add", data=json.dumps(payload), headers=headers)

    assert_rpc_response(response)
    assert {"files", "name", "project_id", "remote_branch"} == set(response.json["result"].keys())

    dest = make_project_path(
        user,
        {
            "owner": url_components.owner,
            "name": url_components.name,
            "slug": url_components.slug,
            "project_id": project_id,
        },
    )
    old_commit = Repository(dest).head.commit
    job_id = response.json["result"]["files"][0]["job_id"]
    commit_message = "service: dataset add remote file"

    dataset_add_remote_file(user, job_id, project_id, True, commit_message, payload["name"], url)

    new_commit = Repository(dest).head.commit

    assert old_commit.hexsha != new_commit.hexsha
    assert commit_message.splitlines()[0] == new_commit.message.splitlines()[0]


@pytest.mark.service
@pytest.mark.integration
@retry_failed
@pytest.mark.vcr
def test_delay_add_file_job(svc_client_cache, it_remote_repo_url_temp_branch, view_user_data):
    """Add a file to a new dataset on a remote repository."""
    from renku.ui.service.serializers.datasets import DatasetAddRequest

    it_remote_repo_url, branch = it_remote_repo_url_temp_branch

    _, _, cache = svc_client_cache
    user = cache.ensure_user(view_user_data)
    renku_module = "renku.ui.service.controllers.datasets_add_file"
    renku_ctrl = "DatasetsAddFileCtrl"

    context = DatasetAddRequest().load(
        {
            "git_url": it_remote_repo_url,
            "branch": branch,
            "name": uuid.uuid4().hex,
            # NOTE: We test with this only to check that recursive invocation is being prevented.
            "is_delayed": True,
            "migrate_project": True,
            "create_dataset": True,
            "files": [{"file_url": "https://tinyurl.com/y6gne4ct"}],
        }
    )

    job = cache.make_job(
        user, job_data={"ctrl_context": {**context, "renku_module": renku_module, "renku_ctrl": renku_ctrl}}
    )

    from renku.ui.service.jobs.delayed_ctrl import delayed_ctrl_job

    updated_job = delayed_ctrl_job(context, view_user_data, job.job_id, renku_module, renku_ctrl)

    assert updated_job
    assert {"remote_branch", "project_id", "files", "name"} == updated_job.ctrl_result["result"].keys()


@pytest.mark.service
@pytest.mark.integration
@retry_failed
def test_delay_add_file_job_failure(svc_client_cache, it_remote_repo_url_temp_branch, view_user_data):
    """Add a file to a new dataset on a remote repository."""
    from renku.ui.service.serializers.datasets import DatasetAddRequest

    it_remote_repo_url, branch = it_remote_repo_url_temp_branch
    _, _, cache = svc_client_cache

    view_user_data["user_id"] = uuid.uuid4().hex
    user = cache.ensure_user(view_user_data)
    renku_module = "renku.ui.service.controllers.datasets_add_file"
    renku_ctrl = "DatasetsAddFileCtrl"

    temp_file = tempfile.NamedTemporaryFile(delete=False)
    temp_file.write(b"data123")
    temp_file.close()

    context = DatasetAddRequest().load(
        {
            "git_url": it_remote_repo_url,
            "branch": branch,
            "name": uuid.uuid4().hex,
            # NOTE: We test with this only to check that recursive invocation is being prevented.
            "is_delayed": True,
            "migrate_project": False,
            "create_dataset": True,
            "files": [{"file_path": temp_file.name}],
        }
    )

    job = cache.make_job(
        user, job_data={"ctrl_context": {**context, "renku_module": renku_module, "renku_ctrl": renku_ctrl}}
    )

    from renku.ui.service.jobs.delayed_ctrl import delayed_ctrl_job

    delayed_ctrl_job(context, view_user_data, job.job_id, renku_module, renku_ctrl)


@pytest.mark.service
@pytest.mark.integration
@retry_failed
def test_delay_create_dataset_job(svc_client_cache, it_remote_repo_url_temp_branch, view_user_data):
    """Create a new dataset successfully."""
    from renku.ui.service.serializers.datasets import DatasetCreateRequest

    it_remote_repo_url, branch = it_remote_repo_url_temp_branch

    context = DatasetCreateRequest().load(
        {
            "git_url": it_remote_repo_url,
            "branch": branch,
            "name": uuid.uuid4().hex,
            # NOTE: We test with this only to check that recursive invocation is being prevented.
            "is_delayed": True,
            "migrate_project": True,
        }
    )

    _, _, cache = svc_client_cache
    renku_module = "renku.ui.service.controllers.datasets_create"
    renku_ctrl = "DatasetsCreateCtrl"

    user = cache.ensure_user(view_user_data)
    job = cache.make_job(
        user, job_data={"ctrl_context": {**context, "renku_module": renku_module, "renku_ctrl": renku_ctrl}}
    )

    from renku.ui.service.jobs.delayed_ctrl import delayed_ctrl_job

    updated_job = delayed_ctrl_job(context, view_user_data, job.job_id, renku_module, renku_ctrl)

    assert updated_job
    assert {"name", "remote_branch"} == updated_job.ctrl_result["result"].keys()


@pytest.mark.service
@pytest.mark.integration
@retry_failed
def test_delay_create_dataset_failure(svc_client_cache, it_remote_repo_url_temp_branch, view_user_data):
    """Create a new dataset successfully."""
    from renku.ui.service.serializers.datasets import DatasetCreateRequest

    it_remote_repo_url, branch = it_remote_repo_url_temp_branch

    context = DatasetCreateRequest().load(
        {
            "git_url": it_remote_repo_url,
            "branch": branch,
            "name": uuid.uuid4().hex,
            # NOTE: We test with this only to check that recursive invocation is being prevented.
            "is_delayed": True,
        }
    )

    _, _, cache = svc_client_cache
    renku_module = "renku.ui.service.controllers.datasets_create"
    renku_ctrl = "DatasetsCreateCtrl"

    view_user_data["user_id"] = uuid.uuid4().hex
    user = cache.ensure_user(view_user_data)
    job = cache.make_job(
        user, job_data={"ctrl_context": {**context, "renku_module": renku_module, "renku_ctrl": renku_ctrl}}
    )

    from renku.ui.service.jobs.delayed_ctrl import delayed_ctrl_job

    delayed_ctrl_job(context, view_user_data, job.job_id, renku_module, renku_ctrl)


@pytest.mark.service
@pytest.mark.integration
@retry_failed
def test_delay_remove_dataset_job(svc_client_cache, it_remote_repo_url_temp_branch, view_user_data):
    """Check a dataset was removed successfully."""
    from renku.ui.service.jobs.delayed_ctrl import delayed_ctrl_job
    from renku.ui.service.serializers.datasets import DatasetRemoveRequest

    it_remote_repo_url, branch = it_remote_repo_url_temp_branch
    _, _, cache = svc_client_cache
    user = cache.ensure_user(view_user_data)

    request_payload = {
        "git_url": it_remote_repo_url,
        "branch": branch,
        "name": "mydata",
        "migrate_project": True,
    }

    context = DatasetRemoveRequest().load(request_payload)
    renku_module = "renku.ui.service.controllers.datasets_remove"
    renku_ctrl = "DatasetsRemoveCtrl"

    delete_job = cache.make_job(
        user, job_data={"ctrl_context": {**context, "renku_module": renku_module, "renku_ctrl": renku_ctrl}}
    )

    updated_job = delayed_ctrl_job(context, view_user_data, delete_job.job_id, renku_module, renku_ctrl)

    assert updated_job
    assert {"name", "remote_branch"} == updated_job.ctrl_result["result"].keys()


@pytest.mark.service
@pytest.mark.integration
@retry_failed
def test_delay_remove_dataset_job_failure(svc_client_cache, it_remote_repo_url_temp_branch, view_user_data):
    """Check removing missing dataset fails."""
    from renku.ui.service.jobs.delayed_ctrl import delayed_ctrl_job
    from renku.ui.service.serializers.datasets import DatasetRemoveRequest

    it_remote_repo_url, ref = it_remote_repo_url_temp_branch
    _, _, cache = svc_client_cache
    user = cache.ensure_user(view_user_data)
    dataset_name = uuid.uuid4().hex

    request_payload = {
        "git_url": it_remote_repo_url,
        "branch": ref,
        "name": dataset_name,
    }

    context = DatasetRemoveRequest().load(request_payload)
    renku_module = "renku.ui.service.controllers.datasets_remove"
    renku_ctrl = "DatasetsRemoveCtrl"

    delete_job = cache.make_job(
        user, job_data={"ctrl_context": {**context, "renku_module": renku_module, "renku_ctrl": renku_ctrl}}
    )

    with pytest.raises(DatasetNotFound):
        delayed_ctrl_job(context, view_user_data, delete_job.job_id, renku_module, renku_ctrl)


@pytest.mark.service
@pytest.mark.integration
@retry_failed
def test_delay_edit_dataset_job(svc_client_cache, it_remote_repo_url_temp_branch, view_user_data):
    """Edit a dataset successfully."""
    from renku.ui.service.serializers.datasets import DatasetEditRequest

    it_remote_repo_url, branch = it_remote_repo_url_temp_branch

    context = DatasetEditRequest().load(
        {
            "git_url": it_remote_repo_url,
            "branch": branch,
            "name": "mydata",
            "title": f"new title => {uuid.uuid4().hex}",
            # NOTE: We test with this only to check that recursive invocation is being prevented.
            "is_delayed": True,
            "migrate_project": True,
        }
    )

    _, _, cache = svc_client_cache
    renku_module = "renku.ui.service.controllers.datasets_edit"
    renku_ctrl = "DatasetsEditCtrl"

    user = cache.ensure_user(view_user_data)
    job = cache.make_job(
        user, job_data={"ctrl_context": {**context, "renku_module": renku_module, "renku_ctrl": renku_ctrl}}
    )

    from renku.ui.service.jobs.delayed_ctrl import delayed_ctrl_job

    updated_job = delayed_ctrl_job(context, view_user_data, job.job_id, renku_module, renku_ctrl)

    assert updated_job
    assert {"warnings", "remote_branch", "edited"} == updated_job.ctrl_result["result"].keys()
    assert {"title"} == updated_job.ctrl_result["result"]["edited"].keys()


@pytest.mark.service
@pytest.mark.integration
@retry_failed
def test_delay_edit_dataset_job_failure(svc_client_cache, it_remote_repo_url_temp_branch, view_user_data):
    """Edit a dataset with a failure."""
    from renku.ui.service.serializers.datasets import DatasetEditRequest

    it_remote_repo_url, branch = it_remote_repo_url_temp_branch

    context = DatasetEditRequest().load(
        {
            "git_url": it_remote_repo_url,
            "branch": branch,
            "name": "mydata",
            "title": f"new title => {uuid.uuid4().hex}",
            "migrate_project": False,
        }
    )

    _, _, cache = svc_client_cache
    renku_module = "renku.ui.service.controllers.datasets_edit"
    renku_ctrl = "DatasetsEditCtrl"

    user = cache.ensure_user(view_user_data)
    job = cache.make_job(
        user, job_data={"ctrl_context": {**context, "renku_module": renku_module, "renku_ctrl": renku_ctrl}}
    )

    from renku.ui.service.jobs.delayed_ctrl import delayed_ctrl_job

    delayed_ctrl_job(context, view_user_data, job.job_id, renku_module, renku_ctrl)


@pytest.mark.service
@pytest.mark.integration
@retry_failed
def test_delay_unlink_dataset_job(svc_client_cache, it_remote_repo_url_temp_branch, view_user_data):
    """Unlink a file from a dataset successfully."""
    from renku.ui.service.serializers.datasets import DatasetUnlinkRequest

    it_remote_repo_url, branch = it_remote_repo_url_temp_branch

    context = DatasetUnlinkRequest().load(
        {
            "git_url": it_remote_repo_url,
            "branch": branch,
            "name": "ds1",
            "include_filters": ["data1"],
            # NOTE: We test with this only to check that recursive invocation is being prevented.
            "is_delayed": True,
            "migrate_project": True,
        }
    )

    _, _, cache = svc_client_cache
    renku_module = "renku.ui.service.controllers.datasets_unlink"
    renku_ctrl = "DatasetsUnlinkCtrl"

    user = cache.ensure_user(view_user_data)
    job = cache.make_job(
        user, job_data={"ctrl_context": {**context, "renku_module": renku_module, "renku_ctrl": renku_ctrl}}
    )

    from renku.ui.service.jobs.delayed_ctrl import delayed_ctrl_job

    updated_job = delayed_ctrl_job(context, view_user_data, job.job_id, renku_module, renku_ctrl)

    assert updated_job
    assert {"unlinked", "remote_branch"} == updated_job.ctrl_result["result"].keys()
    assert ["data/data1"] == updated_job.ctrl_result["result"]["unlinked"]


@pytest.mark.service
@pytest.mark.integration
@retry_failed
def test_delay_unlink_dataset_job_failure(svc_client_cache, it_remote_repo_url_temp_branch, view_user_data):
    """Unlink a file from a dataset failure."""
    from renku.ui.service.serializers.datasets import DatasetUnlinkRequest

    it_remote_repo_url, branch = it_remote_repo_url_temp_branch

    context = DatasetUnlinkRequest().load(
        {"git_url": it_remote_repo_url, "branch": branch, "name": "ds1", "include_filters": ["data1"]}
    )

    _, _, cache = svc_client_cache
    renku_module = "renku.ui.service.controllers.datasets_unlink"
    renku_ctrl = "DatasetsUnlinkCtrl"

    user = cache.ensure_user(view_user_data)
    job = cache.make_job(
        user, job_data={"ctrl_context": {**context, "renku_module": renku_module, "renku_ctrl": renku_ctrl}}
    )

    from renku.ui.service.jobs.delayed_ctrl import delayed_ctrl_job

    delayed_ctrl_job(context, view_user_data, job.job_id, renku_module, renku_ctrl)


@pytest.mark.service
@pytest.mark.integration
@retry_failed
def test_unlink_dataset_sync(svc_client_cache, it_remote_repo_url_temp_branch, view_user_data):
    """Unlink a file from a dataset successfully."""
    from renku.ui.service.serializers.datasets import DatasetUnlinkRequest

    it_remote_repo_url, branch = it_remote_repo_url_temp_branch

    context = DatasetUnlinkRequest().load(
        {
            "git_url": it_remote_repo_url,
            "branch": branch,
            "name": "ds1",
            "include_filters": ["data1"],
            "migrate_project": True,
        }
    )

    _, _, cache = svc_client_cache
    renku_module = "renku.ui.service.controllers.datasets_unlink"
    renku_ctrl = "DatasetsUnlinkCtrl"

    user = cache.ensure_user(view_user_data)
    job = cache.make_job(
        user, job_data={"ctrl_context": {**context, "renku_module": renku_module, "renku_ctrl": renku_ctrl}}
    )

    from renku.ui.service.jobs.delayed_ctrl import delayed_ctrl_job

    updated_job = delayed_ctrl_job(context, view_user_data, job.job_id, renku_module, renku_ctrl)

    assert updated_job
    assert {"unlinked", "remote_branch"} == updated_job.ctrl_result["result"].keys()
    assert ["data/data1"] == updated_job.ctrl_result["result"]["unlinked"]


@pytest.mark.parametrize(
    "renku_domain,dataset_url,result",
    [
        ("renkulab.io", "https://renkulab.io/datasets/abcdefg", True),
        ("gitlab.renkulab.io", "https://renkulab.io/datasets/abcdefg", True),
        ("renkulab.io", "https://dev.renku.ch/datasets/abcdefg", False),
        ("dev.renku.ch", "https://ci-9999.dev.renku.ch/datasets/abcdefg", False),
    ],
)
def test_dataset_gitlab_token_logic(renku_domain, dataset_url, result, monkeypatch):
    """Test that logic for forwarding gitlab tokens works correctly."""
    from renku.ui.service.jobs.datasets import _is_safe_to_pass_gitlab_token

    with monkeypatch.context() as monkey:
        monkey.setenv("RENKU_DOMAIN", renku_domain)

        assert _is_safe_to_pass_gitlab_token("", dataset_url) == result
