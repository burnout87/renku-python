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
"""Check your system and repository for potential problems."""

import traceback

from pydantic import validate_arguments

from renku.command.command_builder.command import Command
from renku.command.util import ERROR

DOCTOR_INFO = """\
Please note that the diagnosis report is used to help Renku maintainers with
debugging if you file an issue. Use all proposed solutions with maximal care
and if in doubt ask an expert around or file an issue. Thanks!
"""


@validate_arguments(config=dict(arbitrary_types_allowed=True))
def _doctor_check(fix: bool, force: bool):
    """Check your system and repository for potential problems.

    Args:
        fix(bool): Whether to apply fixes or just check.
        force(bool): Whether to force-fix some actions.

    Returns:
        Tuple of whether the project is ok or not and list of problems found.
    """
    from renku.command import checks

    is_ok = True
    fixes_available = False
    problems = []

    for check in checks.__all__:
        try:
            ok, has_fix, problems_ = getattr(checks, check)(fix=fix, force=force)
        except Exception:
            ok = False
            has_fix = False
            tb = "\n\t".join(traceback.format_exc().split("\n"))
            problems_ = f"{ERROR}Exception raised when running {check}\n\t{tb}"

        is_ok &= ok
        fixes_available |= has_fix

        if problems_:
            problems.append(problems_)

    return is_ok, fixes_available, "\n".join(problems)


def doctor_check_command(with_fix):
    """Command to check your system and repository for potential problems.

    Args:
        with_fix: Whether to fix found problems or just check.

    Returns:
        Tuple of whether the project is ok or not and list of problems found.
    """
    if with_fix:
        return (
            Command()
            .command(_doctor_check)
            .lock_project()
            .with_database(write=True)
            .require_migration()
            .require_clean()
            .with_commit()
        )
    else:
        return Command().command(_doctor_check).with_database()
