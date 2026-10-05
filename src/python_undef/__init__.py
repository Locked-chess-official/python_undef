"""
python_undef - A utility to generate a header file that undefines non-standard Python macros in pyconfig.h.

Usage:
    python -m python_undef --generate
    This is the main command to generate Python_undef.h and Python_keep.h based on the system's pyconfig.h to the include directly under the package directly.
    python -m python_undef --generate --output <path>
    This command generates Python_undef.h and Python_keep.h and saves it to the specified output path.
    python -m python_undef --include
    This command prints the include path where Python_undef.h is located.
    python -m python_undef --help
    Display this help message.

    You can also generate your project to shield the macros from your project's config.h:
    ```python
    import python_undef
    if python_undef.generate_python_undef_header(
        "path/to/your/project/config.h",
        output_path="path/to/your/project/include",
        project_name="MyProject",
        main_header_macro="MYPROJECT_H",
        main_header_name="myproject.h",
        macro_need_header="MYPROJECT",
        is_standard_macro_rule=your_function
    ):
        print("good")
    else:
        print("bad")
    ```
"""

import os
import re
import datetime
import sys
from pathlib import Path
from typing import Callable

_MACRO_WHITELIST = [
    "_W64",
    "_CRT_NONSTDC_NO_DEPRECATE",
    "_CRT_SECURE_NO_DEPRECATE"
]

def _is_valid_macro_name(macro_name: str):
    """
    Determine whether a macro name is valid using Python's standard library methods.

    Args:
        macro_name: The macro name to check.

    Returns:
        bool: True if it's a valid Python identifier, False otherwise.
    """
    # Empty string is invalid
    if not macro_name:
        return False

    # Use str.isidentifier() to check for valid identifier syntax
    return macro_name.isidentifier()

def _extract_macro_name(line: str):
    """Extract the macro name from a #define line (handles spaces between # and define)."""
    line = line.strip()

    # Match '#', optional spaces, 'define', spaces, and the macro name
    match = re.match(r'^#\s*define\s+([A-Za-z_][A-Za-z0-9_]*)', line)
    if not match:
        return None

    candidate = match.group(1)

    # Validate with standard identifier rules
    if candidate and _is_valid_macro_name(candidate):
        return candidate
    return None

def _is_standard_python_macro(macro_name: str):
    """
    Check whether a macro follows Python's standard naming conventions.
    Rules: Starts with Py, PY, _Py, _PY
    """
    standard_prefixes = ('Py', 'PY', '_Py', '_PY')
    return macro_name.startswith(standard_prefixes) or macro_name in _MACRO_WHITELIST

def _generate_undef_code(macro_name: str, macro_need_header: str="Py"):
    """Generate the code to undefine a macro."""
    return f"""#ifndef {macro_need_header + "_" if macro_need_header else ""}DONOTUNDEF_{macro_name}
#ifdef {macro_name}
#undef {macro_name}
#endif
#ifdef _{macro_need_header + "_" if macro_need_header else ""}FORWARD_DEFINE_{macro_name}
#undef _{macro_need_header + "_" if macro_need_header else ""}FORWARD_DEFINE_{macro_name}
#pragma pop_macro("{macro_name}")
#endif
#endif /* {macro_need_header + "_" if macro_need_header else ""}DONOTUNDEF_{macro_name} */

"""

def _generate_keep_code(macro_name: str, macro_need_header: str="Py"):
    """Generate the code to keep a macro."""
    return f"""#ifndef {macro_need_header + "_" if macro_need_header else ""}DONOTUNDEF_{macro_name}
#ifdef {macro_name}
#define _{macro_need_header + "_" if macro_need_header else ""}FORWARD_DEFINE_{macro_name}
#pragma push_macro("{macro_name}")
#undef {macro_name}
#endif
#endif /* {macro_need_header + "_" if macro_need_header else ""}DONOTUNDEF_{macro_name} */

"""

def generate_python_undef_header(pyconfig_path: str, / ,output_path: str|None=None, project_name: str="Python",
                                 main_header_macro: str="Py_PYTHON_H", main_header_name: str="Python.h", macro_need_header: str="Py",
                                 is_standard_macro_rule: Callable[[str], bool]=_is_standard_python_macro, inside_project: bool=False) -> bool:
    """
    Generate the keep and undef header files based on your config.h.

    Args:
        pyconfig_path: Path to your config.h file.
        output_path: Output file path, defaults to undef and keep header in the current directory.
        project_name: The name of the project, defaults to "Python".
        main_header_macro: The macro that defines the main header, defaults to "Py_PYTHON_H".
        main_header_name: The name of the main header file, defaults to "Python.h".
        macro_need_header: The macro that defines the header that needs to be included, defaults to "Py".
        is_standard_macro_rule: A function that determines whether a macro is standard, defaults to is_standard_python_macro.
        inside_project: Whether the code is inside the project, defaults to False.
    """
    if output_path is None:
        file_dir = os.path.dirname(os.path.abspath(__file__))
        include_dir = Path(file_dir) / 'include'
        undef_output_path = str(include_dir / f'{project_name}_undef.h')
        keep_output_path = str(include_dir / f'{project_name}_keep.h')
        if not include_dir.exists():
            try:
                os.makedirs(f'{file_dir}/include')
            except Exception as e:
                print(f"Error creating include directory: {e}", file=sys.stderr)
                return False
    else:
        if not os.path.isdir(output_path):
            print(f"Error: Output path '{output_path}' is not a directory.", file=sys.stderr)
            return False
        include_dir = Path(output_path)
        undef_output_path = str(include_dir / f'{project_name}_undef.h')
        keep_output_path = str(include_dir / f'{project_name}_keep.h')

    # Read pyconfig.h
    try:
        with open(pyconfig_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except FileNotFoundError:
        print(f"Error: File not found {pyconfig_path}", file=sys.stderr)
        return False
    except Exception as e:
        print(f"Error reading file: {e}", file=sys.stderr)
        return False

    # Collect macros
    macros_to_undef = []
    all_macros = []
    invalid_macros = []

    filename = os.path.basename(pyconfig_path)
    print(f"Analyzing {filename}...")

    for i, line in enumerate(lines, 1):
        macro_name = _extract_macro_name(line)
        if macro_name:
            all_macros.append(macro_name)

            if not is_standard_macro_rule(macro_name):
                macros_to_undef.append(macro_name)
                print(f"Line {i:4d}: Found non-standard macro '{macro_name}'")
        else:
            # Check if line looks like a definition but has invalid name
            line = line.strip()
            if line.startswith('#'):
                m = re.match(r'^#\s*define\s+(\S+)', line)
                if m:
                    candidate = m.group(1)
                    if candidate and not _is_valid_macro_name(candidate):
                        invalid_macros.append((i, candidate))

    # Deduplicate and sort
    macros_to_undef = sorted(set(macros_to_undef))

    # Header section
    undef_header = f"""/*
 * {project_name}_undef.h - Automatically generated macro undefinition header
 *
 * This file is automatically generated from {os.path.basename(pyconfig_path)}
 * Contains macros that may need to be undefined to avoid conflicts with other libraries.
 *
 * WARNING: This is an automatically generated file. Do not edit manually.
{f''' *
 * Usage:
 *   #include <{project_name}_keep.h>
 *   #include <{main_header_name}>
 *   #include <{project_name}_undef.h>
 *   #include <other_library_headers.h>
 *''' if not inside_project else " *"}
 * To preserve specific macros, define before including this header:
 *   #define {macro_need_header + "_" if macro_need_header else ""}DONOTUNDEF_MACRO_NAME
 *
 * Generated from: {os.path.abspath(pyconfig_path)}
 * Generated at: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
 * Total valid macros found: {len(all_macros)}
 * Macros to undef: {len(macros_to_undef)}
 * Invalid macro names skipped: {len(invalid_macros)}
 *
 * Tool: python_undef
 */

#ifndef {macro_need_header + "_" if macro_need_header else ""}{project_name.upper()}_UNDEF_H
#define {macro_need_header + "_" if macro_need_header else ""}{project_name.upper()}_UNDEF_H
{f'''
#ifndef {main_header_macro}
#  error "{project_name}_undef.h must be included *after* {main_header_name}"
#endif
''' if not inside_project else ""}
"""

    keep_header = f"""/*
 * {project_name}_keep.h - Automatically generated macro keep header
 *
 * This file is automatically generated from {os.path.basename(pyconfig_path)}
 * Contains macros that are preserved to avoid conflicts with other libraries.
 *
 * WARNING: This is an automatically generated file. Do not edit manually.
{f''' *
 * Usage:
 *   #include <{project_name}_keep.h>
 *   #include <{main_header_name}>
 *   #include <{project_name}_undef.h>
 *   #include <other_library_headers.h>
 *''' if not inside_project else " *"}
 * To preserve specific macros, define before including this header:
 *   #define {macro_need_header + "_" if macro_need_header else ""}DONOTUNDEF_MACRO_NAME
 *
 * Generated from: {os.path.abspath(pyconfig_path)}
 * Generated at: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
 * Total valid macros found: {len(all_macros)}
 * Macros to keep: {len(macros_to_undef)}
 * Invalid macro names skipped: {len(invalid_macros)}
 *
 * Tool: python_undef
 */

#ifndef {macro_need_header + "_" if macro_need_header else ""}{project_name.upper()}_KEEP_H
#define {macro_need_header + "_" if macro_need_header else ""}{project_name.upper()}_KEEP_H
{f'''
#ifdef {main_header_macro}
#  error "{project_name}_keep.h must be included *before* {main_header_name}"
#endif
''' if not inside_project else ""}
"""

    # Generate undef code sections
    undef_sections = []
    keep_selection = []
    for macro_name in macros_to_undef:
        undef_sections.append(_generate_undef_code(macro_name, macro_need_header))
        keep_selection.append(_generate_keep_code(macro_name, macro_need_header))

    # Footer
    undef_footer = f"""#endif /* {macro_need_header + "_" if macro_need_header else ""}{project_name.upper()}_UNDEF_H */
"""

    keep_footer = f"""#endif /* {macro_need_header + "_" if macro_need_header else ""}{project_name.upper()}_KEEP_H */
"""

    # Write output
    try:
        with open(undef_output_path, 'w', encoding='utf-8', newline='\n') as f:
            f.write(undef_header)
            f.writelines(undef_sections)
            f.write(undef_footer)
        with open(keep_output_path, 'w', encoding='utf-8', newline='\n') as f:
            f.write(keep_header)
            f.writelines(keep_selection)
            f.write(keep_footer)

        print(f"\n{'='*60}")
        print(f"Successfully generated: '{os.path.basename(undef_output_path)}' and '{os.path.basename(keep_output_path)}'")
        print(f"{'='*60}")
        print("Summary:")
        print(f"  - Total valid macro definitions: {len(all_macros)}")
        print(f"  - Macros to undefine: {len(macros_to_undef)}")
        print(f"  - Preserved standard macros: {len(all_macros) - len(macros_to_undef)}")
        print(f"  - Invalid macro names skipped: {len(invalid_macros)}")

        if invalid_macros:
            print(f"\nSkipped invalid macro names:")
            for line_num, invalid_macro in invalid_macros[:10]:  # show only first 10
                print(f"  Line {line_num:4d}: '{invalid_macro}'")
            if len(invalid_macros) > 10:
                print(f"  ... and {len(invalid_macros) - 10} more")

        if macros_to_undef:
            print(f"\nMacros to undefine (first 50):")
            for i, macro in enumerate(macros_to_undef[:50], 1):
                print(f"  {i:3d}. {macro}")
            if len(macros_to_undef) > 50:
                print(f"  ... and {len(macros_to_undef) - 50} more")

        print(f"\nUsage Notes:")
        print(
            (
                "  1. The right include order is:\n"
                f"      #include <{project_name}_keep.h>\n"
                f"      #include <{main_header_name}>\n"
                f"      #include <{project_name}_undef.h>"
            ) if not inside_project else
            (
                f"  1. Include file \"{project_name}_keep.h\" just in \"{main_header_name}\" (just after define \"{main_header_macro}\") and "
                f"\"{project_name}_undef.h\" after including the other your project headers file (before the endif of \"{main_header_macro}\")."
            )
        )
        print(f"  2. Use {macro_need_header + "_" if macro_need_header else ""}DONOTUNDEF_XXX to protect macros that must be kept its definition in \"{main_header_name}\".")
        print(f"  3. Regenerate this file whenever rebuilding {project_name}.")

        return True
    except Exception as e:
        print(f"Error writing file: {e}", file=sys.stderr)
        return False

def main():
    import argparse
    import sysconfig

    parser = argparse.ArgumentParser(
        prog="python -m python_undef",
        description="Generate or locate Python_keep/undef.h based on the system's pyconfig.h.",
    )

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "-g", "--generate",
        action="store_true",
        help="Generate Python_keep/undef.h based on the system's pyconfig.h to the include directory under the package.",
    )
    group.add_argument(
        "-i", "-I", "--include",
        action="store_true",
        help="Print the include path where Python_keep/undef.h is located.",
    )

    parser.add_argument(
        "-o", "--output",
        metavar="<path>",
        default=None,
        help="Output directory for the generated Python_undef.h (only valid with --generate).",
    )

    args = parser.parse_args()

    if args.generate:
        if args.output is not None and not os.path.isdir(args.output):
            parser.error("Specified output path does not exist.")

        include_dir = Path(sysconfig.get_path("include"))
        pyconfig_path = include_dir / "pyconfig.h"

        if not os.path.exists(pyconfig_path):
            print(f"File {pyconfig_path} not found.", file=sys.stderr)
            print("Please ensure the python is standard installation with headers.", file=sys.stderr)
            sys.exit(1)

        success = generate_python_undef_header(str(pyconfig_path), args.output)

        if success:
            print("\n✅ Generation complete!")
            if args.output is None:
                print(
                    f"💡 Tip: Use '{sys.executable} -m python_undef --include' "
                    f"to add this header file path to search path."
                )
            sys.exit(0)
        else:
            print("\n❌ Generation failed!", file=sys.stderr)
            sys.exit(1)

    elif args.include:
        file_dir = os.path.dirname(os.path.abspath(__file__))
        if not (Path(file_dir) / "include" / "Python_undef.h").exists():
            print(
                f"File not found. Use '{sys.executable} -m python_undef --generate' "
                f"to generate the header first.",
                file=sys.stderr,
            )
            sys.exit(1)
        include_path = os.path.abspath(os.path.join(file_dir, "include"))
        print(include_path)
        sys.exit(0)

if __name__ == "__main__":
    main()
