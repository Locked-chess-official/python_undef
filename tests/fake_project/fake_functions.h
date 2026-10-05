/*
 * fake_functions.h - Public function declarations for the fake project.
 *
 * Declaration availability is driven by configuration macros from
 * fake_config.h:
 *   - FP_ENABLE_FEATURE_A (standard)  -> fp_feature_a_enabled() is declared
 *   - HAVE_FORK (non-standard)        -> fp_has_fork_support() is declared
 *
 * Because fake_project.h undefines the HAVE_* macros *after* this header is
 * included, fp_has_fork_support() must still enter the user's code space
 * (declaration is visible), while the HAVE_FORK macro itself must not.
 */

#ifndef FP_FAKE_FUNCTIONS_H
#define FP_FAKE_FUNCTIONS_H

#ifdef __cplusplus
extern "C" {
#endif

/* Target function that is always available. */
int fp_always_available(void);

#ifdef FP_ENABLE_FEATURE_A
/* Target function gated by a *standard* FP_* macro. */
int fp_feature_a_enabled(void);
#endif

#ifdef HAVE_FORK
/* Target function gated by a *non-standard* HAVE_* config macro. */
int fp_has_fork_support(void);
#endif

#ifdef __cplusplus
}
#endif

#endif /* FP_FAKE_FUNCTIONS_H */
