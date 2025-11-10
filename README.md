# Python_undef

## Download

```bash
pip install python_undef
```

## Usage

This will create the file "Python_undef.h"

```bash
python -m python_undef --generate
```

This will output the include path of "Python_undef.h"

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

If you wan't to save the macro, use `#define DONOTUNDEF_macro_name` before include "Python_undef.h" to keep it.

## License

MIT License
