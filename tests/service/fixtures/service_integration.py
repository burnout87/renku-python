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
"""Renku service fixtures for integration testing."""
import contextlib
import json
import shutil
import uuid
from copy import deepcopy
from typing import Generator

import pytest

from renku.core import errors
from renku.infrastructure.repository import Repository
from tests.utils import format_result_exception, modified_environ


@contextlib.contextmanager
def _mock_cache_sync(repository: Repository):
    """Mocks the resetting of the cache since other fixtures perform migrations on the cache without pushing.

    We don't want to undo that temporary migration with an actual cache sync, as it would break tests with
    repeat service calls, if the migration was just done locally in the fixture.
    """
    from renku.ui.service.gateways.repository_cache import LocalRepositoryCache

    current_reference = repository.head.reference if repository.head.is_valid() else repository.head.commit

    def _mocked_repo_reset(self, project, user):
        """Mock repo reset to work with mocked renku save."""
        repository.reset(current_reference, hard=True)

    reset_repo_function = LocalRepositoryCache._maybe_update_cache
    LocalRepositoryCache._maybe_update_cache = _mocked_repo_reset  # type: ignore

    try:
        yield
    finally:
        LocalRepositoryCache._maybe_update_cache = reset_repo_function  # type: ignore


def integration_repo_path(headers, project_id, url_components):
    """Constructs integration repo path."""
    from renku.ui.service.serializers.headers import RequiredIdentityHeaders
    from renku.ui.service.utils import make_project_path

    user = RequiredIdentityHeaders().load(headers)
    project = {
        "project_id": project_id,
        "owner": url_components.owner,
        "name": url_components.name,
        "slug": url_components.slug,
    }

    project_path = make_project_path(user, project)
    return project_path


@contextlib.contextmanager
def integration_repo(headers, project_id, url_components) -> Generator[Repository, None, None]:
    """With integration repo helper."""
    from renku.core.util.contexts import chdir

    repo_path = integration_repo_path(headers, project_id, url_components)
    with chdir(repo_path):
        repository = Repository(repo_path)
        repository.checkout("master")

        yield repository

        if integration_repo_path(headers, project_id, url_components).exists():
            repository.reset(hard=True)
            repository.checkout("master")
            repository.reset(hard=True)
            repository.clean()


@pytest.fixture()
def integration_lifecycle(
    svc_client,
    mock_redis,
    identity_headers,
    it_remote_repo_url,
    it_protected_repo_url,
    it_workflow_repo_url,
    it_remote_old_repo_url,
    request,
):
    """Setup and teardown steps for integration tests."""
    from renku.domain_model.git import GitURL
    from renku.ui.service.cache import cache
    from renku.ui.service.gateways.repository_cache import LocalRepositoryCache
    from renku.ui.service.serializers.headers import RequiredIdentityHeaders

    marker = request.node.get_closest_marker("remote_repo")

    if marker is None or marker.args[0] == "default":
        remote_repo = it_remote_repo_url
    elif marker.args[0] == "protected":
        remote_repo = it_protected_repo_url
    elif marker.args[0] == "workflow":
        remote_repo = it_workflow_repo_url
    elif marker.args[0] == "old":
        remote_repo = it_remote_old_repo_url
    else:
        raise ValueError(f"Couldn't get remote repo for marker {marker.args[0]}")

    url_components = GitURL.parse(remote_repo)

    user_data = RequiredIdentityHeaders().load(identity_headers)
    user = cache.ensure_user(user_data)

    project = LocalRepositoryCache().get(cache, remote_repo, branch=None, user=user, shallow=False)

    yield svc_client, identity_headers, project.project_id, url_components

    # Teardown step: Delete all branches except master (if needed).
    if integration_repo_path(identity_headers, project.project_id, url_components).exists():
        with integration_repo(identity_headers, project.project_id, url_components) as repository:
            try:
                repository.push(remote="origin", refspec=f":{repository.active_branch.name}")
            except errors.GitCommandError:
                pass


@pytest.fixture
def svc_client_setup(integration_lifecycle):
    """Service client setup."""
    svc_client, headers, project_id, url_components = integration_lifecycle

    with integration_repo(headers, project_id, url_components) as repository:
        repository.checkout("master")

        new_branch = uuid.uuid4().hex
        current = repository.branches.add(new_branch)
        repository.checkout(current)

        with _mock_cache_sync(repository):
            yield svc_client, deepcopy(headers), project_id, url_components, repository

        if integration_repo_path(headers, project_id, url_components).exists():
            # NOTE: Some tests delete the repo
            repository.checkout("master")
            repository.branches.remove(current, force=True)
            try:
                # NOTE: try to delete remote branch in case there was a push
                repository.push(remote="origin", refspec=new_branch, delete=True)
            except:  # noqa: E722
                pass


@pytest.fixture
def svc_client_with_repo(svc_client_setup):
    """Service client with a remote repository."""
    svc_client, headers, project_id, url_components, repo = svc_client_setup

    response = svc_client.post(
        "/cache.migrate", data=json.dumps(dict(git_url=url_components.href, skip_docker_update=True)), headers=headers
    )

    assert response.json["result"]

    with _mock_cache_sync(repo):
        yield svc_client, deepcopy(headers), project_id, url_components


@pytest.fixture
def svc_protected_old_repo(svc_synced_client, it_protected_repo_url):
    """Service client with remote protected repository."""
    from renku.ui.service.cache import cache as redis_cache
    from renku.ui.service.gateways.repository_cache import LocalRepositoryCache
    from renku.ui.service.serializers.headers import RequiredIdentityHeaders

    svc_client, identity_headers, cache, user = svc_synced_client

    user_data = RequiredIdentityHeaders().load(identity_headers)
    user = redis_cache.ensure_user(user_data)

    project = LocalRepositoryCache().get(redis_cache, it_protected_repo_url, branch=None, user=user, shallow=False)

    yield svc_client, identity_headers, project.project_id, cache, user, it_protected_repo_url


@pytest.fixture()
def local_remote_repository(svc_client, tmp_path, mock_redis, identity_headers, real_sync):
    """Client with a local remote to test pushes."""
    from renku.core.util.contexts import chdir
    from renku.domain_model import git
    from renku.ui.cli import cli
    from renku.ui.service.cache import cache as redis_cache
    from renku.ui.service.gateways.repository_cache import LocalRepositoryCache
    from renku.ui.service.serializers.headers import RequiredIdentityHeaders
    from tests.fixtures.runners import RenkuRunner

    remote_repo_path = tmp_path / "remote_repo"

    remote_repo = Repository.initialize(remote_repo_path, bare=True)
    remote_repo_checkout_path = tmp_path / "remote_repo_checkout"
    remote_repo_checkout_path.mkdir()

    remote_repo_checkout = Repository.clone_from(url=remote_repo_path, path=remote_repo_checkout_path)

    # NOTE: Mock GitURL parsing for local URL
    def _parse(href):
        return git.GitURL(href=href, regex="", owner="dummy", name="project", slug="project", path=remote_repo_path)

    original_giturl_parse = git.GitURL.parse
    git.GitURL.parse = _parse

    home = tmp_path / "user_home"
    home.mkdir()

    with modified_environ(HOME=str(home), XDG_CONFIG_HOME=str(home)):
        try:
            with remote_repo_checkout.get_configuration(scope="global", writable=True) as global_config:
                global_config.set_value("user", "name", "Renku Bot")
                global_config.set_value("user", "email", "renku@datascience.ch")

            # NOTE: init "remote" repo
            runner = RenkuRunner()
            with chdir(remote_repo_checkout_path):
                result = runner.invoke(
                    cli, ["init", ".", "--template-id", "python-minimal", "--force"], "\n", catch_exceptions=False
                )
                assert 0 == result.exit_code, format_result_exception(result)

                remote = remote_repo_checkout.active_branch.remote_branch.remote
                remote_repo_checkout.push(remote=remote)
        finally:
            try:
                shutil.rmtree(home)
            except OSError:
                pass

            user_data = RequiredIdentityHeaders().load(identity_headers)
            user = redis_cache.ensure_user(user_data)
            remote_url = f"file://{remote_repo_path}"

            project = LocalRepositoryCache().get(redis_cache, remote_url, branch=None, user=user, shallow=False)

            project_id = project.project_id

    try:
        yield svc_client, identity_headers, project_id, remote_repo, remote_repo_checkout, remote_url
    finally:
        git.GitURL.parse = original_giturl_parse

        try:
            shutil.rmtree(remote_repo_path)
        except OSError:
            pass

        try:
            shutil.rmtree(remote_repo_checkout_path)
        except OSError:
            pass


@pytest.fixture
def quick_cache_synchronization(mocker):
    """Forces cache to synchronize on every request."""
    import renku.ui.service.cache.models.project

    mocker.patch.object(renku.ui.service.cache.models.project.Project, "fetch_age", 10000)

    yield
