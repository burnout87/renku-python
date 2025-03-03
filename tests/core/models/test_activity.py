#
# Copyright 2018-2023 - Swiss Data Science Center (SDSC)
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
"""Test Activity."""

from unittest.mock import MagicMock
from uuid import uuid4

from renku.core.util.datetime8601 import local_now
from renku.domain_model.entity import Entity
from renku.domain_model.provenance.activity import Activity
from renku.domain_model.provenance.agent import Person
from renku.domain_model.workflow.parameter import CommandInput, CommandOutput, CommandParameter
from renku.domain_model.workflow.plan import Plan


def test_activity_parameter_values(project_with_injection, mocker):
    """Test parameter values are correctly set on an activity."""

    def get_entity_from_revision_mock(repository, path, revision=None, bypass_cache=False):
        return Entity(checksum="abcdefg", id=uuid4().hex, path=path)

    def get_git_user_mock(repository):
        return Person(id=uuid4().hex, name="John Doe", email="john@doe.com")

    mocker.patch("renku.domain_model.provenance.activity.get_entity_from_revision", get_entity_from_revision_mock)
    mocker.patch("renku.domain_model.provenance.activity.get_git_user", get_git_user_mock)
    commit = MagicMock()
    commit.hexsha.return_value = uuid4().hex
    commit.committer.email.return_value = "john@doe.com"
    commit.committer.name.return_value = "John Doe"

    project_gateway = MagicMock()
    project_gateway.get_project.return_value.id.return_value = "some_project"

    i1 = CommandInput(id="i1", default_value="i1_path")
    i1_copy = CommandInput(id="i2", default_value="i1_path")
    i3 = CommandInput(id="i3", default_value="i3_path")
    i4 = CommandInput(id="i4", default_value="i4_path")
    i4.actual_value = "other_i4_path"

    o1 = CommandOutput(id="o1", default_value="o1_path")
    o1_copy = CommandOutput(id="o2", default_value="o1_path")
    o3 = CommandOutput(id="o3", default_value="o3_path")
    o4 = CommandOutput(id="o4", default_value="o4_path")
    o4.actual_value = "other_o4_path"

    p1 = CommandParameter(id="p1", default_value=1.1)
    p1_copy = CommandParameter(id="p2", default_value=1.1)
    p3 = CommandParameter(id="p3", default_value=3)
    p4 = CommandParameter(id="p4", default_value="4")
    p4.actual_value = "5"

    plan = Plan(
        id="test",
        command="",
        inputs=[i1, i1_copy, i3, i4],
        outputs=[o1, o1_copy, o3, o4],
        parameters=[p1, p1_copy, p3, p4],
    )

    activity = Activity.from_plan(
        plan,
        repository=project_with_injection.repository,
        project_gateway=project_gateway,
        started_at_time=local_now(),
        ended_at_time=local_now(),
        annotations=[],
    )

    assert len(activity.generations) == 3
    assert len(activity.usages) == 3

    assert len(activity.parameters) == 12

    pi1 = next(p for p in activity.parameters if i1.id == p.parameter_id)
    assert pi1.value == i1.default_value

    pi2 = next(p for p in activity.parameters if i1_copy.id == p.parameter_id)
    assert pi2.value == i1_copy.default_value

    pi3 = next(p for p in activity.parameters if i3.id == p.parameter_id)
    assert pi3.value == i3.default_value

    pi4 = next(p for p in activity.parameters if i4.id == p.parameter_id)
    assert pi4.value != i4.default_value
    assert pi4.value == i4.actual_value

    po1 = next(p for p in activity.parameters if o1.id == p.parameter_id)
    assert po1.value == o1.default_value

    po2 = next(p for p in activity.parameters if o1_copy.id == p.parameter_id)
    assert po2.value == o1_copy.default_value

    po3 = next(p for p in activity.parameters if o3.id == p.parameter_id)
    assert po3.value == o3.default_value

    po4 = next(p for p in activity.parameters if o4.id == p.parameter_id)
    assert po4.value != o4.default_value
    assert po4.value == o4.actual_value

    pp1 = next(p for p in activity.parameters if p1.id == p.parameter_id)
    assert pp1.value == p1.default_value

    pp2 = next(p for p in activity.parameters if p1_copy.id == p.parameter_id)
    assert pp2.value == p1_copy.default_value

    pp3 = next(p for p in activity.parameters if p3.id == p.parameter_id)
    assert pp3.value == p3.default_value

    pp4 = next(p for p in activity.parameters if p4.id == p.parameter_id)
    assert pp4.value != p4.default_value
    assert pp4.value == p4.actual_value

    # test getting applied plan
    pi1.value = "pi1"
    pi4.value = "pi4"
    po1.value = "po1"
    po4.value = "po4"
    pp1.value = "pp1"
    pp4.value = "pp4"

    applied_plan = activity.plan_with_values

    assert applied_plan.inputs[0].actual_value == pi1.value
    assert applied_plan.inputs[3].actual_value == pi4.value
    assert applied_plan.outputs[0].actual_value == po1.value
    assert applied_plan.outputs[3].actual_value == po4.value
    assert applied_plan.parameters[0].actual_value == pp1.value
    assert applied_plan.parameters[3].actual_value == pp4.value
