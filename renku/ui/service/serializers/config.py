#
# Copyright 2020 - Swiss Data Science Center (SDSC)
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
"""Renku service config serializers."""

from marshmallow import Schema, fields

from renku.ui.service.serializers.common import AsyncSchema, MigrateSchema, RemoteRepositorySchema, RenkuSyncSchema
from renku.ui.service.serializers.rpc import JsonRPCResponse


class ConfigShowRequest(RemoteRepositorySchema):
    """Request schema for config show."""


class ConfigShowSchema(Schema):
    """Config generic schema."""

    config = fields.Dict(metadata={"description": "Dictionary of configuration items."}, required=True)


class ConfigShowResponse(ConfigShowSchema):
    """Response schema for project config show."""

    default = fields.Dict(metadata={"description": "Dictionary of default configuration items."}, required=True)


class ConfigShowResponseRPC(JsonRPCResponse):
    """RPC response schema for project config show response."""

    result = fields.Nested(ConfigShowResponse)


class ConfigSetRequest(AsyncSchema, ConfigShowSchema, MigrateSchema, RemoteRepositorySchema):
    """Request schema for config set."""


class ConfigSetResponse(ConfigShowSchema, RenkuSyncSchema):
    """Response schema for project config set."""

    default = fields.Dict(metadata={"description": "Dictionary of default configuration items."})


class ConfigSetResponseRPC(JsonRPCResponse):
    """RPC response schema for project config set response."""

    result = fields.Nested(ConfigSetResponse)
