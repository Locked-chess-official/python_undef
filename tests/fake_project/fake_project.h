/*
 * fake_project.h - Public umbrella header for the fake project.
 *
 * This header deliberately mirrors how a real "inside_project" consumer wires
 * in the generated keep/undef headers:
 *
 *   #include <fake_project_keep.h>    <-- right after the guard define
 *   #include "fake_config.h"
 *   #include "fake_functions.h"
 *   #include <fake_project_undef.h>   <-- after all other project headers
 *
 * The generated fake_project_keep.h / fake_project_undef.h are produced by the
 * test suite from fake_config.h using generate_python_undef_header(...,
 * inside_project=True), so this file only references them.
 */

#ifndef FP_FAKE_PROJECT_H
#define FP_FAKE_PROJECT_H

#include "fake_project_keep.h"

#include "fake_config.h"
#include "fake_functions.h"

#include "fake_project_undef.h"

#endif /* FAKE_PROJECT_H */
