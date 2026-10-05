/*
 * fake_config.h - Configuration header for the fake project.
 *
 * This project's *standard* (public) macros use the FP prefix, but the header
 * also carries a handful of non-standard HAVE_* macros (as if a configure
 * script leaked them).  The keep/undef tool must strip only those HAVE_*
 * macros from the project's public surface while preserving FP_* and the
 * FAKE_* include guards.
 */

#ifndef FP_FAKE_CONFIG_H
#define FP_FAKE_CONFIG_H

/* --- standard, FP-prefixed public configuration --- */
#define FP_ENABLE_FEATURE_A 1
#define FP_VERSION_MAJOR 1
#define FP_VERSION_MINOR 2
#define FP_BUFFER_SIZE 256

/* --- non-standard macros that must not leak to user code --- */
#define HAVE_FORK 1
#define HAVE_PIPE 1
#define HAVE_UNISTD_H 1

#endif /* FAKE_CONFIG_H */
