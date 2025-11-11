# Python_undef

This is a Python script that generates a header file "Python_undef.h" which undefine many macros in "pyconfig.h" that doesn't match the rule that "should start with PY_".

## Why

The "pyconfig.h" continue many macros that doesn't math the rule that "should start with PY_" which may cause the comflict with the other projects. This project undefines them.

## Download

```bash
pip install python_undef
```

## Usage

This command under will create the file "Python_undef.h"

```bash
python -m python_undef --generate
```

It defaults output the file "Python_undef.h" in the package directory. You can use the `--output` option to specify the output file:

```bash
python -m python_undef --generate --output <path>
```

The command under will output the include path of "Python_undef.h".

You can use this command in your C/C++ project such as "cmake", "gyp" and so on.

If hadn't run `python -m python_undef --generate` it will exit with code 1.

```bash
python -m python_undef --include
```

You can include the "Python_undef.h" file in your project:

```c
#include <Python.h>
#include <Python_undef.h>
#include <other_header.h>
```

The "pyconfig.h" continue many macros that doesn't math the rule that "should start with PY_". This file undefine them.

If you want to save the macro, use `#define DONOTUNDEF_macro_name` before include "Python_undef.h" to keep it.

## License

MIT License
