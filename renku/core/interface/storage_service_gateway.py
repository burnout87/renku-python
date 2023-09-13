# Copyright Swiss Data Science Center (SDSC)
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
"""Interface for a remote storage service."""

from typing import List, Protocol

from renku.domain_model.cloud_storage import CloudStorage


class IStorageService(Protocol):
    """Interface for a storage service."""

    def ls(self, project_id: str) -> List[CloudStorage]:
        """List storage configured for the current project."""
        ...

    def create(self, storage: CloudStorage) -> CloudStorage:
        """Create a new cloud storage."""
        ...

    def edit(self, storage_id: str, new_storage: CloudStorage) -> None:
        """Edit a cloud storage."""
        ...

    def delete(self, storage_id: str) -> None:
        """Delete a cloud storage."""
        ...

    def validate(self, storage: CloudStorage) -> None:
        """Validate a cloud storage.

        Raises an exception for invalid storage.
        """
        ...
