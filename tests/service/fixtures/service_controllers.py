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
"""Renku service fixtures for controller testing."""
import pytest


@pytest.fixture
def ctrl_init(svc_client_cache):
    """Cache object for controller testing."""
    from renku.ui.service.serializers.headers import RequiredIdentityHeaders

    _, headers, cache = svc_client_cache

    headers["Authorization"] = "Bearer not-a-token"
    user_data = RequiredIdentityHeaders().load(headers)

    return cache, user_data
