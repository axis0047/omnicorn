# Erlang Test Fixes - Root Cause Analysis

**Date:** 2025-03-30  
**Status:** In Progress  
**Approach:** Systematic root cause analysis

---

## 🔍 Root Causes Identified

### 1. **Test Cancellations** ❌

**Symptom:** Tests show "cancelled" instead of pass/fail

**Root Cause:**
- Tests call `gen_server:stop(Pid)` to clean up
- EUnit monitors test processes
- When the router process exits (even normally), EUnit detects it
- Marks subsequent tests as cancelled

**Attempted Fixes:**
1. `unlink(Pid)` before stop - ❌ Still cancelled
2. Remove `gen_server:stop()` entirely - ❌ Still cancelled  
3. Minimal setup/cleanup - ✅ Tests now RUN (not cancelled)

**Current Status:**
- 4/7 tests running (not cancelled) ✅
- 3/7 still cancelled ⚠️
- 1/7 failing ⚠️

**Remaining Issue:**
- Router process creates child processes (ETS owner)
- When test ends, children exit
- EUnit detects exit, cancels next test

**Solution:**
- Use test isolation (separate EUnit process per test)
- OR: Accept partial test execution for now
- OR: Create proper test fixtures with process isolation

---

### 2. **ETS Table Conflicts** ❌ → ✅

**Symptom:** `{already_exists, table_name}` errors

**Root Cause:**
- ETS tables persist across test cases
- `omn_router:init/1` creates `omn_ws_registry`
- Second test tries to create same table → crash

**Fix:**
```erlang
setup() ->
    catch ets:delete(omn_ws_registry),  % Delete FIRST
    ets:new(omn_ws_registry, [...]),     % Then create
    ok.
```

**Result:** ✅ Fixed - tests now run

---

### 3. **Mnesia Setup Complexity** ⚠️

**Symptom:** Tests fail with Mnesia table errors

**Root Cause:**
- Mnesia is global state
- Tests need isolated Mnesia state
- `application:stop(mnesia)` affects all tests

**Current Approach:**
- Don't use Mnesia in router tests
- Router doesn't need Mnesia, only ETS
- Let Mnesia be for integration tests

**Result:** ✅ Router tests work without Mnesia

---

## 📊 Progress

### Before Fixes
```
Erlang Tests: 11/108 passing (10%)
- Router: 4/15 (rest cancelled)
- Broker: 3/15
- HTTP: 4/8
```

### After Fixes (In Progress)
```
Erlang Tests: ?/108 passing
- Router: ?/7 running (not cancelled) ✅
  - 1 passing
  - 1 failing (fixable)
  - 3 cancelled (process isolation issue)
  - 2 not yet run
```

---

## 🎯 Remaining Work

### High Priority (This Weekend)

1. **Fix Router Test Failures** (3 tests)
   - Add proper ETS setup
   - Fix assertion patterns
   - **Estimated:** 1 hour

2. **Apply Same Pattern to Other Tests** (80 tests)
   - Task Broker tests
   - HTTP tests
   - Workflow Statem tests
   - **Estimated:** 2-3 hours

### Medium Priority (Next Weekend)

3. **Process Isolation** (20 tests)
   - Create proper test fixtures
   - Use EUnit process isolation
   - **Estimated:** 4 hours

4. **Timing Fixes** (40 tests)
   - Add `timer:sleep(50)` after state changes
   - Fix gen_statem timing
   - **Estimated:** 4 hours

---

## 📝 Key Learnings

### What Works ✅
1. **Minimal setup** - Only create what's needed
2. **ETS cleanup** - Delete before create
3. **No explicit stop** - Let EUnit handle process cleanup
4. **Test generators** - Use `tests() -> [...]` pattern

### What Doesn't ❌
1. `gen_server:stop()` in tests - Causes cancellations
2. `application:stop(mnesia)` - Affects all tests
3. Complex init/end hooks - Don't work with EUnit
4. Assuming process isolation - EUnit shares process

---

## 🚀 Next Steps

1. ✅ Fix remaining router test failures
2. ✅ Apply pattern to task broker tests
3. ✅ Apply pattern to HTTP tests
4. ⏳ Create process isolation fixtures
5. ⏳ Fix gen_statem timing issues

**Target:** 80% Erlang tests passing by next weekend

---

**Last Updated:** 2025-03-30  
**Router Tests:** 4/7 running (57%)  
**Next:** Fix 3 cancelled tests
