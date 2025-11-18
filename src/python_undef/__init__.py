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
        nonstandare_macro_rule=your_function
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

MACRO_WRITELIST = [
    "_W64",
    "_CRT_NONSTDC_NO_DEPRECATE",
    "_CRT_SECURE_NO_DEPRECATE"
]

def is_valid_macro_name(macro_name: str):
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

def extract_macro_name(line: str):
    """Extract the macro name from a #define line (handles spaces between # and define)."""
    line = line.strip()

    # Match '#', optional spaces, 'define', spaces, and the macro name
    match = re.match(r'^#\s*define\s+([A-Za-z_][A-Za-z0-9_]*)', line)
    if not match:
        return None

    candidate = match.group(1)

    # Validate with standard identifier rules
    if candidate and is_valid_macro_name(candidate):
        return candidate
    return None

def is_standard_python_macro(macro_name: str):
    """
    Check whether a macro follows Python's standard naming conventions.
    Rules: Starts with Py, PY, _Py, _PY
    """
    standard_prefixes = ('Py', 'PY', '_Py', '_PY')
    return macro_name.startswith(standard_prefixes) or macro_name in MACRO_WRITELIST

def generate_undef_code(macro_name: str, macro_need_header: str="Py"):
    """Generate the code to undefine a macro."""
    return f"""#ifndef DONOTUNDEF_{macro_name}
#ifdef {macro_name}
#undef {macro_name}
#endif
#ifdef _{macro_need_header}_FORWARD_DEFINE_{macro_name}
#undef _{macro_need_header}_FORWARD_DEFINE_{macro_name}
#pragma pop_macro("{macro_name}")
#endif
#endif

"""

def generate_keep_code(macro_name: str, macro_need_header: str="Py"):
    """Generate the code to keep a macro."""
    return f"""#ifndef DONOTUNDEF_{macro_name}
#ifdef {macro_name}
#define _{macro_need_header}_FORWARD_DEFINE_{macro_name}
#pragma push_macro("{macro_name}")
#undef {macro_name}
#endif
#endif

"""

def generate_python_undef_header(pyconfig_path: str, / ,output_path: str|None=None, project_name: str="Python",
                                 main_header_macro: str="Py_PYTHON_H", main_header_name: str="Python.h", macro_need_header: str="Py",
                                 nonstandare_macro_rule: Callable[[str], bool]=is_standard_python_macro, inside_project: bool=False):
    """
    Generate the keep and undef header files based on your config.h.
    
    Args:
        pyconfig_path: Path to your config.h file.
        output_path: Output file path, defaults to undef and keep header in the current directory.
        project_name: The name of the project, defaults to "Python".
        main_header_macro: The macro that defines the main header, defaults to "Py_PYTHON_H".
        main_header_name: The name of the main header file, defaults to "Python.h".
        macro_need_header: The macro that defines the header that needs to be included, defaults to "Py".
        nonstandare_macro_rule: A function that determines whether a macro is non-standard, defaults to is_standard_python_macro.
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
        macro_name = extract_macro_name(line)
        if macro_name:
            all_macros.append(macro_name)

            # New rule: any macro not starting with Py/PY/_Py/_PY and not ending with _H is considered non-standard
            if not nonstandare_macro_rule(macro_name):
                macros_to_undef.append(macro_name)
                print(f"Line {i:4d}: Found non-standard macro '{macro_name}'")
        else:
            # Check if line looks like a define but has invalid name
            line = line.strip()
            if line.startswith('#'):
                m = re.match(r'^#\s*define\s+(\S+)', line)
                if m:
                    candidate = m.group(1)
                    if candidate and not is_valid_macro_name(candidate):
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
 *   #define DONOTUNDEF_MACRO_NAME
 *
 *
 * Generated from: {os.path.abspath(pyconfig_path)}
 * Generated at: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
 * Total valid macros found: {len(all_macros)}
 * Macros to undef: {len(macros_to_undef)}
 * Invalid macro names skipped: {len(invalid_macros)}
 *
 * Tool: python_undef
 */

#ifndef {project_name.upper()}_UNDEF_H
#define {project_name.upper()}_UNDEF_H
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
 *   #define DONOTUNDEF_MACRO_NAME
 *
 * Generated from: {os.path.abspath(pyconfig_path)}
 * Generated at: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
 * Total valid macros found: {len(all_macros)}
 * Macros to keep: {len(all_macros) - len(macros_to_undef)}
 *
 * Tool: python_undef
 */

#ifndef {project_name.upper()}_KEEP_H
#define {project_name.upper()}_KEEP_H
{f'''
#ifdef {main_header_macro}
#error "{project_name}_keep.h must be included *before* {main_header_name}"
#endif

''' if not inside_project else ""}
"""

    # Generate undef code sections
    undef_sections = []
    keep_selection = []
    for macro_name in macros_to_undef:
        undef_sections.append(generate_undef_code(macro_name, macro_need_header))
        keep_selection.append(generate_keep_code(macro_name, macro_need_header))

    # Footer
    undef_footer = f"""#endif /* {project_name.upper()}_UNDEF_H */
"""

    keep_footer = f"""#endif /* {project_name.upper()}_KEEP_H */
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
                f"  1. Include file \"{project_name}_undef.h\" and \"{project_name}_keep.h\" before including other library headers"
                f", but \"{project_name}_undef.h\" must be after '<{main_header_name}>'."
            ) if not inside_project else 
            (
                f"  1. Include file \"{project_name}_keep.h\" before including \"{os.path.basename(pyconfig_path)}\" and "
                f"\"{project_name}_undef.h\" after including the other your project headers file."
            )
        )
        print(f"  2. Use DONOTUNDEF_XXX to protect macros that must be kept its defination in \"{main_header_name}\".")
        print(f"  3. Regenerate this file whenever rebuilding {project_name}.")

        return True
    except Exception as e:
        print(f"Error writing file: {e}", file=sys.stderr)
        return False

def main():
    import sysconfig
    if sys.argv[1:]:
        if sys.argv[1] in ('-h', '--help'):
            print("""Usage:
python -m python_undef --generate
    Generate Python_undef.h based on the system's pyconfig.h to the include directly under the package directly.
python -m python_undef --generate --output <path>
    Generate Python_undef.h and specify output path.
python -m python_undef --include
    Print the include path where Python_undef.h is located.""")
            sys.exit(0)
        elif sys.argv[1] == '--generate': 
            include_dir = Path(sysconfig.get_path('include'))
            print(f"\n{'='*60}")
            print("Note: Python keywords are not excluded since they are valid macro names in C/C++.")
            print(f"{'='*60}")

            pyconfig_path = include_dir / "pyconfig.h"

            if os.path.exists(pyconfig_path):
                if sys.argv[2:]:
                    if sys.argv[2] == "--output" and len(sys.argv) == 4:
                        if not os.path.isdir(sys.argv[3]):
                            print("Error: Specified output path does not exist.", file=sys.stderr)
                            sys.exit(1)
                        output_path = sys.argv[3]
                        print(f"Output path specified: {output_path}")
                    else:
                        print("Invalid output argument. Use --output <path> to specify output file.", file=sys.stderr)
                        sys.exit(1)
                else:
                    output_path = None
                success = generate_python_undef_header(pyconfig_path, output_path)

                if success:
                    print(f"\n✅ Generation complete!")
                    if output_path is None:
                        print(f"💡 Tip: Use '{sys.executable} -m python_undef --include' to add this header file path to search path.")
                    sys.exit(0)
                else:
                    print(f"\n❌ Generation failed!", file=sys.stderr)
                    sys.exit(1)

            else:
                print(f"File {pyconfig_path} not found.", file=sys.stderr)
                print("Please ensure the python is standard installation with headers.", file=sys.stderr)
                sys.exit(1)
        elif sys.argv[1] == "--include":
            file_dir = os.path.dirname(os.path.abspath(__file__))
            if not (Path(file_dir) / "include" / "Python_undef.h").exists():
                print(f"File not found. Use '{sys.executable} -m python_undef --generate' to generate the header first.", file=sys.stderr)
                sys.exit(1)
            include_path = os.path.abspath(os.path.join(file_dir, 'include'))
            print(include_path)
            sys.exit(0)
        else:
            print("Unknown argument. Use --help for usage information.", file=sys.stderr)
            sys.exit(1)
    else:
        print("No arguments provided. Use --help for usage information.", file=sys.stderr)
        sys.exit(1)
