#
# Copyright 2017-2023 - Swiss Data Science Center (SDSC)
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
"""Test ``session`` commands."""

import re
from unittest.mock import patch

import click
import pytest

from renku.core.errors import ParameterError, RenkulabSessionError
from renku.core.plugin.session import get_supported_session_providers
from renku.core.session.docker import DockerSessionProvider
from renku.core.session.renkulab import RenkulabSessionProvider
from renku.core.session.session import session_list, session_start, session_stop, ssh_setup
from renku.core.util.ssh import SystemSSHConfig
from renku.domain_model.session import SessionStopStatus


def fake_start(
    self,
    image_name,
    project_name,
    config,
    cpu_request,
    mem_request,
    disk_request,
    gpu_request,
    **kwargs,
):
    return "0xdeadbeef", ""


def fake_stop(self, project_name, session_name, stop_all):
    if session_name == "missing_session":
        return SessionStopStatus.FAILED
    return SessionStopStatus.SUCCESSFUL


def fake_find_image(self, image_name, config):
    if image_name == "missing_image":
        return False
    return True


def fake_build_image(self, image_descriptor, image_name, config):
    return


def fake_session_list(self, project_name):
    return ["0xdeadbeef"]


def fake_pre_start_checks(self, **kwargs):
    pass


def fake_force_build_image(self, **kwargs):
    return kwargs.get("force_build", False)


@pytest.mark.parametrize(
    "provider_name,session_provider,provider_patches",
    [
        ("docker", DockerSessionProvider, {}),
        ("renkulab", RenkulabSessionProvider, {}),
    ],
)
@pytest.mark.parametrize(
    "parameters,result",
    [
        ({}, "0xdeadbeef"),
        ({"image_name": "fixed_image"}, "0xdeadbeef"),
        ({"image_name": "missing_image"}, click.Abort),
        (({"image_name": "missing_image", "force_build": True}, "0xdeadbeef")),
    ],
)
def test_session_start(
    run_shell,
    project,
    provider_name,
    session_provider,
    provider_patches,
    parameters,
    result,
    with_injection,
    mock_communication,
):
    """Test starting sessions."""
    with patch.multiple(
        session_provider,
        session_start=fake_start,
        find_image=fake_find_image,
        build_image=fake_build_image,
        pre_start_checks=fake_pre_start_checks,
        force_build_image=fake_force_build_image,
        **provider_patches,
    ):
        provider_implementation = next(
            filter(lambda x: x.name == provider_name, get_supported_session_providers()), None
        )
        assert provider_implementation is not None

        with with_injection():
            if not isinstance(result, str) and issubclass(result, Exception):
                with pytest.raises(result):
                    session_start(provider=provider_name, config_path=None, **parameters)
            else:
                session_start(provider=provider_name, config_path=None, **parameters)
                assert result in mock_communication.stdout_lines


@pytest.mark.parametrize(
    "provider_name,session_provider,provider_patches",
    [
        ("docker", DockerSessionProvider, {}),
        ("renkulab", RenkulabSessionProvider, {}),
    ],
)
@pytest.mark.parametrize(
    "parameters,result",
    [
        ({"session_name": "0xdeadbeef"}, None),
        ({"session_name": "0xdeadbeef", "stop_all": True}, None),
        ({"session_name": "missing_session"}, ParameterError),
    ],
)
def test_session_stop(
    run_shell, project, with_injection, session_provider, provider_name, parameters, provider_patches, result
):
    """Test stopping sessions."""
    with patch.multiple(session_provider, session_stop=fake_stop, **provider_patches):
        provider_implementation = next(
            filter(lambda x: x.name == provider_name, get_supported_session_providers()), None
        )
        assert provider_implementation is not None

        with with_injection():
            if result is not None and issubclass(result, Exception):
                with pytest.raises(result):
                    session_stop(provider=provider_name, **parameters)
            else:
                session_stop(provider=provider_name, **parameters)


@pytest.mark.parametrize(
    "provider_name,session_provider,provider_patches",
    [
        ("docker", DockerSessionProvider, {}),
        ("renkulab", RenkulabSessionProvider, {}),
    ],
)
@pytest.mark.parametrize("provider_exists,result", [(True, ["0xdeadbeef"]), (False, ParameterError)])
def test_session_list(
    project,
    provider_name,
    session_provider,
    provider_patches,
    provider_exists,
    result,
    with_injection,
):
    """Test listing sessions."""
    with patch.multiple(session_provider, session_list=fake_session_list, **provider_patches):
        with with_injection():
            provider = provider_name if provider_exists else "no_provider"

            if not isinstance(result, list) and issubclass(result, Exception):
                with pytest.raises(result):
                    session_list(provider=provider)
            else:
                output = session_list(provider=provider)
                assert output.sessions == result


def test_session_ssh_setup(project, with_injection, fake_home, mock_communication):
    """Test setting up SSH config for a deployment."""
    with patch("renku.core.util.ssh.get_renku_url", lambda: "https://renkulab.io/"):
        with with_injection():
            ssh_setup()

    ssh_home = fake_home / ".ssh"
    renku_ssh_path = ssh_home / "renku"
    assert renku_ssh_path.exists()
    assert re.search(r"Include .*/\.ssh/renku/\*\.conf", (ssh_home / "config").read_text())
    assert (renku_ssh_path / "99-renkulab.io-jumphost.conf").exists()
    assert (renku_ssh_path / "renkulab.io-key").exists()
    assert (renku_ssh_path / "renkulab.io-key.pub").exists()
    assert len(mock_communication.confirm_calls) == 0

    key = (renku_ssh_path / "renkulab.io-key").read_text()

    with patch("renku.core.util.ssh.get_renku_url", lambda: "https://renkulab.io/"):
        with with_injection():
            with pytest.raises(click.Abort):
                ssh_setup()

    assert len(mock_communication.confirm_calls) == 1
    assert key == (renku_ssh_path / "renkulab.io-key").read_text()

    with patch("renku.core.util.ssh.get_renku_url", lambda: "https://renkulab.io/"):
        with with_injection():
            ssh_setup(force=True)

    assert key != (renku_ssh_path / "renkulab.io-key").read_text()


def test_session_start_ssh(project, with_injection, mock_communication, fake_home):
    """Test starting of a session with SSH support."""
    from renku.domain_model.project_context import project_context

    def _fake_send_request(self, req_type: str, *args, **kwargs):
        class _FakeResponse:
            status_code = 200

            def json(self):
                return {"name": "0xdeadbeef"}

        return _FakeResponse()

    with patch.multiple(
        RenkulabSessionProvider,
        find_image=fake_find_image,
        build_image=fake_build_image,
        _wait_for_session_status=lambda _, __, ___: None,
        _send_renku_request=_fake_send_request,
        _remote_head_hexsha=lambda _: project.repository.head.commit.hexsha,
        _renku_url=lambda _: "example.com",
        _cleanup_ssh_connection_configs=lambda _, __: None,
        _auth_header=lambda _: None,
    ):
        provider_implementation = next(filter(lambda x: x.name == "renkulab", get_supported_session_providers()), None)
        assert provider_implementation is not None

        with patch("renku.core.util.ssh.get_renku_url", lambda: "https://renkulab.io/"):
            with with_injection():
                ssh_setup()
                supported = project_context.project.template_metadata.ssh_supported

                try:
                    project_context.project.template_metadata.ssh_supported = False
                    with pytest.raises(expected_exception=RenkulabSessionError, match="project doesn't support SSH"):
                        session_start(provider="renkulab", config_path=None, ssh=True)
                finally:
                    project_context.project.template_metadata.ssh_supported = supported

        with patch("renku.core.util.ssh.get_renku_url", lambda: "https://renkulab.io/"):
            with with_injection():
                supported = project_context.project.template_metadata.ssh_supported

                try:
                    project_context.project.template_metadata.ssh_supported = True
                    session_start(provider="renkulab", config_path=None, ssh=True)
                finally:
                    project_context.project.template_metadata.ssh_supported = supported

        assert any("0xdeadbeef" in line for line in mock_communication.stdout_lines)
        ssh_home = fake_home / ".ssh"
        renku_ssh_path = ssh_home / "renku"
        assert (renku_ssh_path / "99-renkulab.io-jumphost.conf").exists()
        assert (project.path / ".ssh" / "authorized_keys").exists()
        assert len(list(renku_ssh_path.glob("00-*-0xdeadbeef.conf"))) == 1


def test_session_ssh_configured(project, with_injection, fake_home):
    """Test that the SSH class correctly determines if a session is configured for SSH."""
    from renku.domain_model.project_context import project_context

    with patch("renku.core.util.ssh.get_renku_url", lambda: "https://renkulab.io/"):
        with with_injection():
            system_config = SystemSSHConfig()

            assert not system_config.is_session_configured("my-session-abcdefg")

            previous_commit = project_context.repository.head.commit

            project_context.ssh_authorized_keys_path.parent.mkdir(parents=True, exist_ok=True)
            project_context.ssh_authorized_keys_path.touch()
            project_context.repository.add(project_context.ssh_authorized_keys_path)
            intermediate_commit = project_context.repository.commit("Add auth keys file")

            assert not system_config.is_session_configured("my-session-abcdefg")
            assert not system_config.is_session_configured(f"my-session-{previous_commit}")
            assert not system_config.is_session_configured(f"my-session-{intermediate_commit}")

            key = "my-key"
            system_config.public_keyfile.write_text(key)
            project_context.ssh_authorized_keys_path.write_text(f"\n{key} Renku Bot")
            project_context.repository.add(project_context.ssh_authorized_keys_path)
            valid_commit = project_context.repository.commit("Add auth keys file")
            assert system_config.is_session_configured(f"my-session-{valid_commit}")
