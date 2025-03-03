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
"""Renku service fixtures for cache management."""
import pytest


@pytest.fixture(scope="function")
def mock_redis():
    """Monkey patch service cache with mocked redis."""
    from _pytest.monkeypatch import MonkeyPatch

    from renku.core.util import git
    from renku.ui.service.cache.base import BaseCache
    from renku.ui.service.cache.models.file import File, FileChunk
    from renku.ui.service.cache.models.job import Job
    from renku.ui.service.cache.models.project import Project
    from renku.ui.service.cache.models.user import User
    from renku.ui.service.jobs.queues import WorkerQueues

    def push_changes_mock(*_, **__):
        """Mock for repository remote sync."""
        return "origin"

    monkey_patch = MonkeyPatch()
    with monkey_patch.context() as m:
        import fakeredis

        fake_redis = fakeredis.FakeRedis(server=fakeredis.FakeServer())
        from walrus import Database

        fake_model_db = Database(connection_pool=fake_redis.connection_pool)

        m.setattr(WorkerQueues, "connection", fake_redis)
        m.setattr(BaseCache, "cache", fake_redis)
        m.setattr(BaseCache, "model_db", fake_model_db)

        m.setattr(Job, "__database__", fake_model_db)
        m.setattr(User, "__database__", fake_model_db)
        m.setattr(File, "__database__", fake_model_db)
        m.setattr(FileChunk, "__database__", fake_model_db)
        m.setattr(Project, "__database__", fake_model_db)

        git.push_changes = push_changes_mock

        yield

    monkey_patch.undo()
