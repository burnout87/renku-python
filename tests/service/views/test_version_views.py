#
# Copyright 2020-2023 -Swiss Data Science Center (SDSC)
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
"""Renku service version view tests."""
from renku.core.migration.migrate import SUPPORTED_PROJECT_VERSION
from renku.ui.service.views.api_versions import MAXIMUM_VERSION, MINIMUM_VERSION


def test_version(svc_client):
    """Test expected response from version endpoint."""
    from renku import __version__

    response = svc_client.get("/apiversion")
    assert "result" in response.json
    data = response.json["result"]

    assert {"latest_version", "supported_project_version", "minimum_api_version", "maximum_api_version"} == set(
        data.keys()
    )
    assert __version__ == data["latest_version"]
    assert SUPPORTED_PROJECT_VERSION == data["supported_project_version"]
    assert MINIMUM_VERSION.name == data["minimum_api_version"]
    assert MAXIMUM_VERSION.name == data["maximum_api_version"]

    response = svc_client.get("/1.0/apiversion")
    assert "result" in response.json
    data = response.json["result"]

    assert {"latest_version", "supported_project_version", "minimum_api_version", "maximum_api_version"} == set(
        data.keys()
    )
    assert __version__ == data["latest_version"]
    assert SUPPORTED_PROJECT_VERSION == data["supported_project_version"]
    assert MINIMUM_VERSION.name == data["minimum_api_version"]
    assert MAXIMUM_VERSION.name == data["maximum_api_version"]

    response = svc_client.get("/1.1/apiversion")
    assert "result" in response.json
    data = response.json["result"]

    assert {"latest_version", "supported_project_version", "minimum_api_version", "maximum_api_version"} == set(
        data.keys()
    )
    assert __version__ == data["latest_version"]
    assert SUPPORTED_PROJECT_VERSION == data["supported_project_version"]
    assert MINIMUM_VERSION.name == data["minimum_api_version"]
    assert MAXIMUM_VERSION.name == data["maximum_api_version"]

    response = svc_client.get("/1.2/apiversion")
    assert "result" in response.json
    data = response.json["result"]

    assert {"latest_version", "supported_project_version", "minimum_api_version", "maximum_api_version"} == set(
        data.keys()
    )
    assert __version__ == data["latest_version"]
    assert SUPPORTED_PROJECT_VERSION == data["supported_project_version"]
    assert MINIMUM_VERSION.name == data["minimum_api_version"]
    assert MAXIMUM_VERSION.name == data["maximum_api_version"]

    response = svc_client.get("/2.0/apiversion")
    assert "result" in response.json
    data = response.json["result"]

    assert {"latest_version", "supported_project_version", "minimum_api_version", "maximum_api_version"} == set(
        data.keys()
    )
    assert __version__ == data["latest_version"]
    assert SUPPORTED_PROJECT_VERSION == data["supported_project_version"]
    assert MINIMUM_VERSION.name == data["minimum_api_version"]
    assert MAXIMUM_VERSION.name == data["maximum_api_version"]
