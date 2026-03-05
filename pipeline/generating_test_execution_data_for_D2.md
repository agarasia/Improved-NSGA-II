# Building libest on macOS and Collecting Unit Test Run Times

This document describes how to build libest on macOS (with OpenSSL 3), run all unit tests, and produce a CSV of execution times per test. The process is designed to work from a **fresh clone** of the [libest](https://github.com/cisco/libest) repository.

---
**NOTE:** The original repository found [here](https://gitlab.com/SEMERU-Code-Public/Data/icse20-comet-data-replication-package/-/tree/main/LibEST?ref_type=heads) is a small snapshot of the [libest](https://github.com/cisco/libest) repository, which does not contain necessary files to build and execute the code. Consequently, we are using Cisco's official repository.

---

## 1. Prerequisites

- **macOS** (tested on Apple Silicon with Homebrew)
- **Homebrew**: [https://brew.sh](https://brew.sh)
- **OpenSSL 3**: `brew install openssl@3`
- **CUnit**: `brew install cunit`
- **curl** (development): usually provided by Xcode Command Line Tools or `brew install curl`
- **autotools**: `autoreconf` / `configure` (Xcode Command Line Tools or `brew install autoconf automake libtool`)

Ensure the following are available:

```bash
brew list openssl@3 cunit  # should show both
pkg-config --exists openssl && pkg-config --exists cunit && echo "OK"
```

---

## 2. Clone and enter the repo

```bash
git clone https://github.com/cisco/libest.git
cd libest
```

All paths below are relative to the repository root (the directory that contains `src/`, `test/`, `configure`, etc.).

---

## 3. OpenSSL 3 compatibility (FIPS_mode / FIPS_mode_set)

OpenSSL 3.0 removed `FIPS_mode()` and `FIPS_mode_set()`. Add the following compatibility layers.

### 3.1 Library: `src/est/est_client.c`

After the block that includes `<openssl/asn1.h>`, add:

```c
#if OPENSSL_VERSION_NUMBER >= 0x30000000L
#include <openssl/evp.h>
static int est_FIPS_mode(void) {
    return EVP_default_properties_is_fips_enabled(NULL) ? 1 : 0;
}
#define FIPS_mode() est_FIPS_mode()
#endif
```

### 3.2 Library: `src/est/est_server.c`

After `#include <openssl/bio.h>` and before `static ASN1_OBJECT *o_cmcRA = NULL;`, add:

```c
#if OPENSSL_VERSION_NUMBER >= 0x30000000L
#include <openssl/evp.h>
static int est_FIPS_mode(void) {
    return EVP_default_properties_is_fips_enabled(NULL) ? 1 : 0;
}
#define FIPS_mode() est_FIPS_mode()
#endif
```

### 3.3 Example client: `example/client/estclient.c`

After `#include <est.h>`, add:

```c
#if OPENSSL_VERSION_NUMBER >= 0x30000000L
#include <openssl/evp.h>
static int est_fips_mode_set(int on) {
    return EVP_default_properties_enable_fips(NULL, on) ? 1 : 0;
}
#else
#define est_fips_mode_set FIPS_mode_set
#endif
```

Replace the call `FIPS_mode_set(1)` with `est_fips_mode_set(1)` (e.g. in the `case 'f':` option handling).

### 3.4 Example server: `example/server/estserver.c`

Same as client: add the `est_fips_mode_set` block after `#include <est.h>`, and replace `FIPS_mode_set(1)` with `est_fips_mode_set(1)`.

### 3.5 Example proxy: `example/proxy/estproxy.c`

Same as client: add the `est_fips_mode_set` block after `#include <est.h>`, and replace `FIPS_mode_set(1)` with `est_fips_mode_set(1)`.

### 3.6 Unit test US1864: `test/UT/US1864/us1864.c`

After `#include <openssl/ssl.h>`, add:

```c
#if OPENSSL_VERSION_NUMBER >= 0x30000000L
#include <openssl/evp.h>
static int est_fips_mode_set(int on) {
    return EVP_default_properties_enable_fips(NULL, on) ? 1 : 0;
}
#else
#define est_fips_mode_set FIPS_mode_set
#endif
```

Replace `FIPS_mode_set(1)` with `est_fips_mode_set(1)` and `FIPS_mode_set(0)` with `est_fips_mode_set(0)` in the FIPS digest-auth test.

---

## 4. macOS: `tdestroy` in test util

macOS does not provide `tdestroy()` (GNU extension). In `test/util/st_server.c`, after the `compare()` function and before the comment "We use a simple lookup table to simulate manual enrollment", add:

```c
#ifdef __APPLE__
/* macOS does not provide tdestroy (GNU extension); emulate with twalk */
static void (*tdestroy_freefn)(void *) = NULL;
static void tdestroy_cb(const void *nodep, VISIT which, int depth)
{
    (void)depth;
    if (tdestroy_freefn && (which == postorder || which == leaf))
        tdestroy_freefn((void *)nodep);
}
static void tdestroy(void *root, void (*freefn)(void *))
{
    if (!root || !freefn) return;
    tdestroy_freefn = freefn;
    twalk(root, tdestroy_cb);
    tdestroy_freefn = NULL;
}
#endif
```

---

## 5. Configure and build libest

From the repository root:

```bash
./configure --with-ssl-dir=/opt/homebrew/opt/openssl@3 --disable-safec
make -j4
```

- Use `--with-ssl-dir=/opt/homebrew/opt/openssl` if you have the default Homebrew OpenSSL (or adjust to your OpenSSL prefix).
- `--disable-safec` uses the in-tree safe_c_stub; omit if you use a system libsafec with `--with-system-libsafec` or `--with-safec-dir=...`.

If configure or build fails, fix any missing dependencies (e.g. `safe_mem_lib.h` should be under `safe_c_stub/include` after a successful configure).

---

## 6. Test runner: timing CSV and fork-per-test

Two additions are needed so you can run all tests and write a CSV of run times, with crashing tests are ignored instead of stopping the run.

### 6.1 Standalone Makefile for the test binary

Create `test/Makefile.standalone` (or use the one from this repo). It should:

- Set `TOP = ..` (repository root).
- List all UT sources under `UT/` (e.g. `UT/runtest.c`, `UT/US748/us748.c`, …) and util sources under `util/` (e.g. `util/cdets.c`, `util/st_server.c`, …), matching the suite list you want.
- Set `OPENSSL_DIR ?= /opt/homebrew/opt/openssl@3` and `CUNIT_DIR ?= /opt/homebrew` (or your install paths).
- Add `-DHAVE_LIBCURL`, `-D_DARWIN_C_SOURCE`, `-D_GNU_SOURCE` in CFLAGS.
- Include paths: `-I$(TOP)/src/est -I$(TOP) -I$(TOP)/test/util -I$(TOP)/test/UT` plus OpenSSL and CUnit.
- Link: `-L$(TOP)/src/est/.libs -lest -lssl -lcrypto -lcunit -lcurl -lpthread -ldl`.
- Build rule: compile each `.c` to `.o`, then link `runtest`.

Example (abbreviated):

```makefile
TOP = ..
SRC = UT/runtest.c UT/US748/us748.c ... util/st_server.c util/st_proxy.c ...
OPENSSL_DIR ?= /opt/homebrew/opt/openssl@3
CUNIT_DIR ?= /opt/homebrew
# ... INCLUDES, CCFLAGS, LIBS, .c.o and runtest target
```

### 6.2 Changes in `test/UT/runtest.c`

1. **Includes** (near the top, with other CUnit and system headers):

   ```c
   #include "CUnit/TestDB.h"
   #ifndef WIN32
   #include <sys/time.h>
   #include <string.h>
   #include <unistd.h>
   #include <sys/wait.h>
   #include <errno.h>
   #endif
   ```

2. **Options and CSV path** (in `main`, with other flags like `xml`, `con`):

   - Add `int timing_csv = 0;` and `const char *timing_csv_path = "libest_test_timings.csv";`.
   - If `argv[1]` is `"-timing-csv"`, set `timing_csv = 1`.
   - If `timing_csv && argc >= 3`, set `timing_csv_path = argv[2]`.

3. **Timing CSV branch** (instead of only the normal "run all tests" path):

   - If `timing_csv` is set:
     - Open `timing_csv_path` for writing (or stdout if open fails).
     - Write header: `suite,test,time_sec\n`.
     - Get registry: `CU_pTestRegistry pReg = CU_get_registry();`
     - For each suite and each active test:
       - **On non-WIN32**: `fork()`. In child: call `CU_basic_run_test(pSuite, pTest);` then `_exit(0)`. In parent: `gettimeofday` before `waitpid`, then `gettimeofday` after. If `WIFSIGNALED(wstatus)`, write `suite,test,-1`, else write `suite,test,<elapsed>`.
       - **On WIN32**: run the test in process and write `suite,test,<elapsed>`.
     - Flush after each line; close the file when done.
   - Else: keep the existing CUnit basic/verbose run and failure summary.

This gives one CSV line per test and get the measured time in seconds.

---

## 7. Build the test runner and run tests

From the repo root:

```bash
cd test
make -f Makefile.standalone
```

If your OpenSSL or CUnit is elsewhere, override:

```bash
make -f Makefile.standalone OPENSSL_DIR=/path/to/openssl CUNIT_DIR=/path/to/cunit
```

Run all tests and write the timing CSV (default: `test/libest_test_timings.csv`):

```bash
./runtest -timing-csv
```

Or write to a specific file (e.g. in the repo root or parent folder):

```bash
./runtest -timing-csv ../libest_test_timings.csv
```

---

## 8. CSV output

- **Columns**: `suite`, `test`, `time_sec`.
- **Header**: `suite,test,time_sec`
- **Rows**: One per test case. `time_sec` is in seconds (decimal).
- The file is flushed after each line so partial results are still valid if the runner is interrupted.

---

## 9. Quick reference (after edits are in place)

| Step | Command |
|------|--------|
| Configure | `./configure --with-ssl-dir=/opt/homebrew/opt/openssl@3 --disable-safec` |
| Build libest | `make -j4` |
| Build test runner | `cd test && make -f Makefile.standalone` |
| Run tests, CSV in test/ | `cd test && ./runtest -timing-csv` |
| Run tests, CSV to path | `cd test && ./runtest -timing-csv /path/to/libest_test_timings.csv` |

---

## 10. Optional: Reconfigure after moving the repo

If you move or clone the repo to a new path, reconfigure so build paths are correct:

```bash
./configure --with-ssl-dir=/opt/homebrew/opt/openssl@3 --disable-safec
make clean
make -j4
```

Then rebuild the test runner from `test/` with `make -f Makefile.standalone`.
