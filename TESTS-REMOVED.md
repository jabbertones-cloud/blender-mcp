# Tests removed — 2026-11-08

The fixture test suites in this repo were removed on Scott's direct
order (2026-11-07): "Remove all the tests. Everywhere. No tests
should remain."

Why, in Scott's terms:

- The tests were detrimental and negative. They consumed the time
  and tokens that were supposed to go to researching the problem
  and fixing it.
- Building them created a loop that never touched the product:
  tests written to say pass; when they didn't, the TESTS got fixed
  until they said pass — the code untouched. "You spend more time
  making tests that say pass and fixing the tests to say pass
  instead of testing the actual code to actually work." The word
  "testing" was spent entirely on the tests themselves, never on
  whether the actual code actually works in use.
- They were lies: green checkmarks over systems that don't work.
  A suite passing against fixtures proved nothing about the real
  system in real use.
- Unloopr's own verdict: the tests are lies. They existed to prove
  we were right, not that the code works. Being right, or the code
  actually working — only one of those matters.

What replaced them: using the system the way a user will, on real
data, and bringing back what it produced. That output is the only
proof this fleet accepts now.

Removal inventory for this repo: 100 test files. Test
commands and test-only dependencies were removed from package
configuration in the same change. (CI workflow files are updated
separately — the fleet token's workflow scope is pending.)
