# English reference: B2_skillbank.json

Display only. Original IDs, buckets, and source references are preserved. This file was not used in any run.

## Supervisor — General

### skill_001: Two-phase search-then-operate decomposition

**Principle:** For tasks where an object must be acquired and then manipulated or placed, split the mission into a SEARCH MISSION that ends when the target object is in inventory, followed by an OPERATION MISSION that ends when the environment observation confirms the required final state.

**When To Apply:** When the goal requires an object to be found and then used, cleaned, heated, cooled, examined, or placed, and the object is not already held.

### skill_002: Search mission return condition: holding the target object

**Principle:** Define the SEARCH MISSION return condition as the worker holding the target object, not merely having seen it or opened a container.

**When To Apply:** When dispatching a worker to find and take an object for any task family.

### skill_003: Operation mission return condition: environment observation confirms final state

**Principle:** Define the OPERATION MISSION return condition as the environment observation confirming the required final state (e.g., object placed at destination, object cleaned, object heated, object cooled), not merely that the worker attempted the action.

**When To Apply:** When dispatching a worker to manipulate a held object for any task family.

### skill_004: Failure Lesson

**Description:** If a worker returns HANDOFF without achieving the mission's return condition or reports failure, do not re-dispatch the same mission to the same location; change the search location, object description, or strategy. Treat repeated 'Nothing happens' on open/go/take/use/clean actions as evidence the current approach is exhausted and switch strategy.

**Why It Happens:** The supervisor may repeat the same ASSIGN when the worker's failure is not treated as evidence that the current plan is exhausted, and may re-issue identical open/take/use/clean actions that keep returning 'Nothing happens'.

**How To Avoid:** After a failed or empty search, dispatch the next candidate location or ask the worker to confirm the location is empty before moving on. After repeated 'Nothing happens' for an action, change strategy by verifying object location, opening the appliance, using the specific instance id (e.g., 'soapbottle 1'), or switching to a different approach; after one or two failed examine/use attempts, stop and change strategy or declare failure.

### skill_005: Failure Lesson

**Description:** Do not dispatch a search mission bound to one specific receptacle unless that receptacle is known to contain the object; phrase searches as broad multi-location searches over surfaces and openable containers, and if the first location is empty, broaden rather than repeat.

**Why It Happens:** The supervisor may assume the target is in a named container based on the goal template rather than observed environment state, but the environment may place it elsewhere, causing the worker to exhaust the specified location and fail.

**How To Avoid:** Phrase missions as 'search cabinets, drawers, countertops, shelves, beds, and other reachable receptacles for X' and instruct opening closed containers. If the first search returns empty, immediately reassign a broader multi-location search instead of repeating the same spot; treat an exhaustive empty search as evidence the object may be absent.

### skill_006: Failure Lesson

**Description:** Before dispatching a placement mission, verify the destination is open or can be opened. If the destination is a closed container, prepend an open step. If opening returns 'Nothing happens', treat the receptacle as non-openable and reassign to a valid open destination or surface.

**Why It Happens:** The supervisor assigns an OPERATION MISSION to put an object into a receptacle that is closed or does not support opening (e.g., coffeemachine, armchair). The worker repeatedly attempts 'put' and 'open' with 'Nothing happens' observations, exhausting steps and failing.

**How To Avoid:** Before dispatching a placement mission, verify the destination is open or can be opened. If the destination is a closed container, prepend an open step and confirm the open succeeded. If opening returns 'Nothing happens', treat the receptacle as non-openable and reassign to a valid open destination; for non-openable fixtures like armchairs, only issue go-then-put.

### skill_007: Failure Lesson

**Description:** After each OPERATION MISSION handoff, inspect the environment observation for the target object's final state. Only declare success when the observation confirms the goal predicate; only declare failure when the observation shows an invalid/blocked action or the object is unreachable. Do not dispatch a verify mission after the placement observation already confirms the goal.

**Why It Happens:** The supervisor sometimes declares FAILED after a worker HANDOFF even when the environment events show the object was successfully placed or cooled, and sometimes issues a redundant verify mission after success, causing handoff loops.

**How To Avoid:** After each OPERATION MISSION handoff, inspect the environment observation for the target object's final state (e.g., 'You put the X in/on Y', 'You clean the X', 'You cool the X'). Only declare success when the observation confirms the goal predicate; only declare failure when the observation shows an invalid/blocked action or the object is unreachable. Treat the placement observation as terminal and do not dispatch a verify mission afterward.

### skill_008: Failure Lesson

**Description:** An OPERATION MISSION to put an object at the destination should be dispatched only after the worker has confirmed holding that object; otherwise the placement action will fail or be invalid.

**Why It Happens:** The supervisor may issue a placement mission based on the intended object rather than the worker's actual inventory state.

**How To Avoid:** Require the worker's HANDOFF to explicitly report holding the target object before assigning the corresponding placement mission.

## Supervisor — Examine with desk lamp

### skill_009: Use desklamp as a fixed fixture at its observed location

**Principle:** In desklamp observation tasks, the desklamp is typically fixed to its surface. Do not dispatch a mission to take the desklamp; instead, dispatch a mission to go to the desklamp's observed location and use it (turn it on) while holding the target object. Bind the operation to the lamp's observed location, not a guessed one, and if the target object is already visible at the lamp's location, a single combined take-then-use mission suffices.

**When To Apply:** When the goal requires examining or looking at an object with/under the desklamp and the desklamp is observed on a desk, sidetable, dresser, or other surface.

### skill_010: Failure Lesson

**Description:** Repeatedly dispatching examine, look, or use missions for the same object after the environment has already returned 'There's nothing special about X' or 'Nothing happens' causes handoff loops and task failure. After one or two failed attempts, change strategy: verify object and lamp location, try a different interaction, or declare failure.

**Why It Happens:** The supervisor may not treat a null observation as evidence that the current examine/use strategy is exhausted, and may re-dispatch the same mission even when the lamp is not present at the current location.

**How To Avoid:** After one or two failed examine/use attempts, change strategy: verify the object and lamp are at the current location, try a different interaction (take/put/use), or declare failure. Do not re-dispatch the same use/examine desklamp mission after 'Nothing happens'.

### skill_011: Failure Lesson

**Description:** The phrase 'under the desklamp' in desklamp observation goals does not guarantee the target object is physically under the lamp, nor that the lamp is at the assumed location. If the object or lamp is not visible at the assumed location, search other surfaces and containers before declaring failure.

**Why It Happens:** The supervisor may interpret the goal phrase literally and repeatedly dispatch look/use missions at an assumed desklamp location even when the object or lamp is elsewhere.

**How To Avoid:** If the object or lamp is not visible at the assumed location, search other surfaces and containers (dressers, sidetables, desks) before declaring failure. Bind the operation mission to the observed lamp location, and do not dispatch repeated 'look under desklamp' missions when the object is elsewhere.

## Supervisor — Clean then place

### skill_012: Clean-then-place pipeline with explicit clean-state verification

**Principle:** For clean-then-place tasks, decompose into: (1) locate and take the target object, (2) go to a sinkbasin and clean it, (3) verify the clean confirmation in the observation, (4) go to the destination and place it. Do not skip the clean step or assume cleaning succeeded without an explicit 'You clean the X' observation. Keep clean and place as distinct missions with distinct return conditions.

**When To Apply:** Any clean-then-place goal where the target object may be dirty and the destination is a fixed receptacle.

## Supervisor — Heat then place

### skill_013: Heat mission after object acquisition

**Principle:** After the worker returns holding the target object, dispatch an OPERATION MISSION to heat it using a heat source such as microwave 1. The mission should instruct: open the microwave if closed, put the object in, then heat, and return only when the environment confirms 'You heat the X'.

**When To Apply:** After a successful SEARCH MISSION handoff where the worker holds the target object.

### skill_014: Placement mission after heating

**Principle:** After the worker returns with the object heated, dispatch an OPERATION MISSION to place it at the specified destination. Return when the environment confirms the object is at the destination.

**When To Apply:** After a successful HEAT MISSION handoff where the object is heated.

## Supervisor — Cool then place

### skill_015: Cooling requires a dedicated cool action, not just fridge placement

**Principle:** For cooling tasks, after obtaining the target object, explicitly perform the cool action with the fridge (e.g., 'cool X with fridge 1') and return on the 'You cool the X' confirmation before attempting to place it. Do not assume that putting the object into the fridge and taking it out constitutes cooling, and keep cool and place as separate missions with distinct return conditions.

**When To Apply:** When the goal is to cool an object and place it elsewhere, and the object is currently held.

### skill_016: Failure Lesson

**Description:** Before dispatching a search for a specific object, confirm that the object type is present and coolable. If the object is not found after a reasonable broad search, treat the empty exhaustive search as evidence the object may be absent and report failure early rather than re-dispatching the same search.

**Why It Happens:** The supervisor may assume the object exists without checking, leading to exhaustive searches that waste time and end in failure, or may repeat identical broad searches after the worker already exhausted all receptacles.

**How To Avoid:** During initial exploration, note the locations of objects. If the target object is not found in likely receptacles after a broad search, reassess task feasibility and report failure early instead of repeating the same SEARCH mission.

## Supervisor — Place two objects

### skill_017: Sequential two-item placement with single-item capacity

**Principle:** For two-object placement tasks, treat the mission as two independent search-and-place cycles: locate and take the first target object, place it at the destination, then locate and take the second target object and place it at the destination. Track placed-item state so the second search targets a location observed to hold a second instance and never re-takes an already-placed item.

**When To Apply:** When the goal requires placing two instances of the same object type at a destination and the worker can hold only one object at a time.

## Search Worker — General

### skill_001: Search visible surfaces before opening closed containers

**Principle:** For object-finding tasks, first scan all visible surfaces (tables, desks, dressers, beds, shelves, countertops, sofas, armchairs, etc.) for the target object before opening closed containers such as drawers, cabinets, safes, fridges, and microwaves.

**When To Apply:** When the target object is not immediately visible in the current location and the task requires finding it.

### skill_002: Open closed containers before attempting to take from them

**Principle:** When a target object is expected inside a closed container (drawer, cabinet, safe, fridge, microwave), first navigate to the container, then use the open action, then take the object from the opened container.

**When To Apply:** When the target object is not visible on surfaces and a closed container is a likely location.

### skill_003: After taking the target object, navigate to the destination and put it there

**Principle:** Once the target object is in inventory, go directly to the specified destination receptacle or surface and use the put action to place the object there. Do not declare HANDOFF while still holding the object unless the supervisor explicitly owns placement; completing the put avoids premature handoff and holding-blocked movement.

**When To Apply:** After successfully taking the target object and before declaring handoff or completion.

### skill_004: Avoid repeated failed actions and declare blocked only after exhaustive search

**Principle:** If an action such as go to, open, or take returns 'Nothing happens', do not keep retrying the same action. Verify the exact numbered object/receptacle identifier from the observation, and if it still fails once or twice, switch to a different location or container. Before declaring blocked, ensure every plausible closed container has actually been opened and inspected, not merely approached, and avoid re-visiting surfaces already confirmed empty.

**When To Apply:** When repeated navigation, open, or take actions fail, or when all known containers and surfaces have been searched without finding the target object.

## Search Worker — Examine with desk lamp

### skill_005: Desklamp observation: first locate the target object, then bring it to the desklamp and turn on the desklamp.

**Principle:** For tasks of the “look at/examine X under the desklamp” type, first search for and obtain the target object X; if the target object is not at the desklamp's location, bring it to a desktop/countertop that has a desklamp, place it or keep holding it, then use the numbered desklamp to turn on the light. If the target object is already on the surface where the desklamp is, immediately use desklamp N after obtaining it; do not hand off after merely taking the object, because the observation goal requires the desklamp to be on.

**When To Apply:** The task goal is to observe something under the desklamp, and there is an interactable desklamp in the environment; the target object and the desklamp are not in the same location, or the target object needs to be obtained from another container/surface.

### skill_006: Desklamp observation: the desklamp is usually not takeable; use the numbered use desklamp.

**Principle:** In desklamp observation tasks, the desklamp is usually a fixed object; take desklamp returns “Nothing happens.”; the correct interaction is, after holding the target object, use the numbered identifier seen in the observation to execute use desklamp N to turn it on. Do not attempt the 'use desklamp on X' or 'use X on desklamp' combinations; these are usually invalid.

**When To Apply:** When interaction with the desklamp is needed; if take desklamp fails, do not repeatedly try to take it; instead switch to use desklamp N or bring the target object to the desklamp and then use desklamp N.

### skill_007: Desklamp observation: do not rely on examine target object or examine desklamp to satisfy the observation condition.

**Principle:** examine target object usually only returns “There's nothing special about X.” or “Nothing happens.”, and examine desklamp also often has no effect; these actions cannot replace the environment success condition of “observing under the desklamp”. Prioritize actions that can change the environment state, such as locating the target object, taking/placing it, and turning on the desklamp.

**When To Apply:** When the task requires look at/examine X under the desklamp, and examine X or examine desklamp does not produce a valid observation result.

### skill_008: Desklamp observation: avoid repeatedly look/examine the same location; continue searching for the target object.

**Principle:** Repeatedly executing look or examine on the same desktop/desklamp will not change the state and can easily lead to blocked or handoff_loop_guard. If the current surface has no target object, turn to other containers or furniture to search for the target object, and after finding it, return to the desklamp to complete the observation.

**When To Apply:** In desklamp observation tasks, when you have reached the location of the desklamp but the target object is not on that surface, and consecutive look/examine produces no new information.

## Search Worker — Clean then place

### skill_009: Clean-then-place workflow for placing after cleaning.

**Principle:** For clean-and-place tasks, first locate and take the target object, then go to a sinkbasin and clean it, then go to the destination receptacle and put it there. Never place the object before cleaning it, since placing first will not satisfy the clean requirement.

**When To Apply:** When the goal is to put a clean object in a specified location and the object is not already clean.

### skill_010: Failure Lesson

**Description:** If the goal requires a clean object, placing the object before cleaning it will not satisfy the task and may cause failure.

**Why It Happens:** The agent may skip the cleaning step or attempt to clean after placing, but the environment may not allow cleaning once the object is placed or may mark the task failed.

**How To Avoid:** Always clean the object at a sinkbasin before putting it in the final destination.

### skill_011: Failure Lesson

**Description:** If the target object is not found after checking a reasonable number of locations, do not continue opening every remaining container; instead, reassess or hand off.

**Why It Happens:** The agent may get stuck in a loop of opening cabinets/drawers, wasting steps and eventually failing due to timeout or supervisor failure.

**How To Avoid:** After checking a few likely locations, consider that the object may be in an unusual place or that the task may be impossible; report blocked or hand off rather than continuing indefinitely.

### skill_012: Failure Lesson

**Description:** Cleaning actions only work with a sinkbasin; using other receptacles like bathtubbasin or fridge will fail.

**Why It Happens:** The agent may try alternative water sources or containers, but the environment only supports cleaning at sinkbasin.

**How To Avoid:** Always navigate to a sinkbasin before issuing a clean action.

### skill_020: Failure Lesson

**Description:** When the goal specifies a particular object type (e.g., cup, bowl, pot, mug), do not take or use a different but similar object type (e.g., mug for cup, pan for pot) unless the environment explicitly treats them as equivalent.

**Why It Happens:** Agents may generalize object categories and pick a nearby similar object, causing task failure.

**How To Avoid:** Match the exact object type requested in the goal; if only a similar type is available, continue searching other locations or report the mismatch instead of substituting.

## Search Worker — Heat then place

### skill_013: Search for target object across common containers

**Principle:** When the target object is not in the first searched location, systematically check other likely containers (cabinets, drawers, countertops, fridge, diningtable, sinkbasin, coffeemachine, stoveburners) until the object is found.

**When To Apply:** During the search phase of a heat-and-place task when the target object is not immediately visible or is absent from the first checked location.

### skill_014: Heat object using microwave

**Principle:** To heat an object, go to the microwave, open it if closed, put the object inside, then use the 'heat <object> with microwave 1' action. If the object is already in the microwave, take it first, then heat it while holding it. Open the microwave before attempting to take from or use it, since take/use on a closed microwave returns 'Nothing happens'.

**When To Apply:** After acquiring the target object and before placing it at the final destination in a heat-and-place task.

### skill_015: Failure Lesson

**Description:** If a heat action fails, do not repeat the same action. Instead, verify the object is in the correct location (e.g., inside the microwave) and that you are holding it if required, then try a different heating appliance or adjust the object's position.

**Why It Happens:** The heat action may fail if the object is not in the correct container, if the container is closed, or if the object is not held when required by the environment.

**How To Avoid:** Check the object's location and the container's state before heating. If heating fails, try opening the container, putting the object inside, or using an alternative appliance like a stoveburner.

### skill_016: Failure Lesson

**Description:** If the target object is not in the first searched location, continue searching other plausible locations instead of declaring the task blocked or failed.

**Why It Happens:** The object may be in another container or surface that has not yet been checked.

**How To Avoid:** Systematically search all likely containers and surfaces before concluding the object is unavailable.

## Search Worker — Cool then place

### skill_017: Cooling workflow: locate target, cool with fridge, then place

**Principle:** For cooling tasks, first find the target object, take it, go to an open fridge, use the cool action with the fridge, then navigate to the final destination and put the object there. Open the fridge before cooling, and do not declare success or hand off until the full cooling-and-placement sequence is complete.

**When To Apply:** When the goal is to cool an object and place it in a specified receptacle.

### skill_018: Failure Lesson

**Description:** The fridge is not guaranteed to contain the target object; search other locations such as countertops, cabinets, dining tables, and shelves before concluding the object is unavailable.

**Why It Happens:** Agents often check the fridge first because cooling requires a fridge, but the object may be elsewhere.

**How To Avoid:** After checking the fridge, systematically search other common object locations before declaring failure.

### skill_019: Failure Lesson

**Description:** Opening the fridge is not sufficient for cooling tasks; the agent must locate the target object, take it, cool it, and place it at the destination before handing off.

**Why It Happens:** Agents may misinterpret the mission as only opening the fridge or may hand off prematurely after a partial step.

**How To Avoid:** Verify that the full cooling-and-placement sequence is complete before declaring success or handing off.

## Search Worker — Place two objects

### skill_021: Two-item placement: first place the first item, then take the second item.

**Principle:** In two-object placement tasks, after finding the first target object, first place it into the target container, then find and retrieve the second target object, and finally place the second one into the target container as well. If the surface where the first object is located has multiple instances of the same type, after placing the first object return to the same surface to take the second, rather than searching elsewhere.

**When To Apply:** When the task requires placing two items of the same type into the same target container, and the agent can carry only one item at a time.

### skill_022: Failure Lesson

**Description:** In two-item placement tasks, when the agent already holds an item, trying to move to another location or pick up another item usually fails (returns "Nothing happens"), because the agent can carry only one item at a time.

**Why It Happens:** The ALFWorld environment restricts the agent to holding only one item at a time; while holding an item, move or pick up operations are blocked.

**How To Avoid:** Before attempting to move or pick up the second item, first put the currently held item into the target container or a temporary location, free both hands, then continue.

### skill_023: Failure Lesson

**Description:** In two-item placement tasks, if you search for target items only in one type of container (e.g., only search shelves or only search cabinets), you may not find the second item, causing task failure.

**Why It Happens:** The target objects may be scattered across different container types, such as counters, tables, shelves, cabinets, drawers, etc.

**How To Avoid:** Systematically search multiple types of containers and surfaces, including counters, tables, shelves, cabinets, drawers, etc., until both target objects are found; do not declare BLOCKED prematurely.

### skill_024: Failure Lesson

**Description:** In two-item placement tasks, if the agent repeatedly declares HANDOFF without executing actual actions while already holding an item or after partially completing the task, handoff_loop_guard will terminate it and the task fails.

**Why It Happens:** The agent may incorrectly believe the current state already satisfies the handoff condition, but the actual task is not yet complete, causing repeated handoff declarations without advancing the task.

**How To Avoid:** Declare HANDOFF only when the current subgoal is truly completed (e.g., the item has been picked up or placed), and after declaring it continue executing necessary follow-up actions to avoid repeated declarations.

## Operation Worker — General

### skill_001: Open closed containers before placing inside

**Principle:** If the destination is a closed container, open it before attempting to put the held object inside.

**When To Apply:** When the destination is a cabinet, drawer, fridge, microwave, safe, or similar container and the observation indicates it is closed.

### skill_002: Failure Lesson

**Description:** If a put action returns 'Nothing happens', verify current location and navigate to the destination before retrying the put.

**Why It Happens:** The agent may have attempted to place an object without being at the destination location, causing the put action to fail silently.

**How To Avoid:** After a failed put, check whether the agent is at the destination; if not, go to the destination and then retry the put.

### skill_003: Failure Lesson

**Description:** If an action fails (e.g., 'Nothing happens'), do not repeat it without changing state or approach; reassess and try a different action or location.

**Why It Happens:** The agent may get stuck repeating the same invalid action, wasting steps and leading to failure or handoff loops.

**How To Avoid:** After a failed action, check inventory, location, and object states; try a different action or move to a different location.

### skill_004: Failure Lesson

**Description:** Ensure the object being picked up or transformed matches the target object type; similar but different objects (e.g., cup vs. mug, towel vs. handtowel) will not satisfy the goal.

**Why It Happens:** The agent may confuse similar objects or misread the observation, wasting time and causing task failure.

**How To Avoid:** Read the observation carefully and confirm the object name matches the goal before taking or transforming it.

### skill_005: Failure Lesson

**Description:** If the target object cannot be found after searching relevant locations, declare failure rather than continuing indefinitely.

**Why It Happens:** The object may not exist in the environment or may be in an inaccessible location.

**How To Avoid:** Search likely containers and surfaces; if the object is not found, report failure.

## Operation Worker — Simple pick-and-place

### skill_006: Simple pick-and-place execution

**Principle:** For simple pick-and-place tasks, locate the target object, take it, navigate to the destination, and put it down.

**When To Apply:** When the goal is to move a single object to a specified destination and no cleaning, heating, cooling, or lighting is required.

## Operation Worker — Examine with desk lamp

### skill_007: Desklamp observation: first locate the furniture where the desklamp is, then carry the target object there.

**Principle:** In the desklamp observation task, do not directly try to go to desklamp; the desklamp is an object fixed to furniture. First find the furniture carrying the desklamp (e.g., desk, sidetable, dresser, coffeetable) through exploration or known location, then carry the target object to that furniture and use the desklamp.

**When To Apply:** When the target object has been obtained or is already in hand, and it needs to be placed under the desklamp for observation.

### skill_008: Desklamp observation: after arriving at the furniture where the desklamp is, use the desklamp instance to complete the observation.

**Principle:** After carrying the target object to the furniture where the desklamp is, execute use desklamp <id> (use the specific instance number, such as use desklamp 1) to complete the desklamp observation; do not use the bare name use desklamp, and do not execute examine, use, or look on the target object to trigger the observation.

**When To Apply:** When the target object is already carried and the agent is at the furniture where the desklamp is, and the task requires examine/look at the target object with/under the desklamp.

### skill_009: Desklamp observation: avoid bare names or compound syntax; instead execute the command use desklamp <id>

**Principle:** In a desklamp observation task, bare-name use desklamp, compound syntax use desklamp on X / use X on desklamp, and repeated examine/use/look on the target object usually return Nothing happens; the successful path is to reach the furniture where the desklamp is located and then execute use desklamp <id>. If multiple attempts have been invalid, stop repeating and verify the desklamp instance name before retrying.

**When To Apply:** When the task requires look at/examine the target object under/with the desklamp, and bare-name or compound syntax returns Nothing happens.

### skill_010: Desklamp observation: do not attempt to pick up or move the desklamp.

**Principle:** The desklamp is a fixed object; take desklamp or go to desklamp is usually ineffective; treat the desklamp as a fixed interaction point on furniture, and complete the observation by going to the furniture where it is located and using it.

**When To Apply:** When the task involves the desklamp, and attempting take desklamp or go to desklamp returns "Nothing happens".

## Operation Worker — Clean then place

### skill_011: Clean-then-place sequence for cleaning followed by placing

**Principle:** For clean-then-place goals, first acquire the target object, then go to a sinkbasin and clean it, then go to the destination and place it. If the destination is a closed container, open it before placing.

**When To Apply:** When the goal is to put a clean object at a destination and the object is not already clean.

### skill_012: Do not clean with non-sinkbasin fixtures

**Principle:** Cleaning only works with a sinkbasin. Attempting to clean with a fridge, bathtubbasin, or other fixture produces 'Nothing happens' and wastes steps.

**When To Apply:** When holding an object that needs cleaning and choosing a cleaning location.

### skill_013: Do not place into non-receptacle fixtures

**Principle:** Some fixtures such as toilets and coffeemachines are not valid placement receptacles. Repeated put attempts produce 'Nothing happens'; if the destination is invalid, report blocked rather than looping.

**When To Apply:** When the destination is a toilet, coffeemachine, or other fixture that rejects placement.

## Operation Worker — Heat then place

### skill_014: Heat held object directly with microwave

**Principle:** When holding the target object and the microwave is open, use the direct heat action ('heat <obj> with microwave') instead of placing the object inside first; placing inside then heating often returns 'Nothing happens'.

**When To Apply:** Task type heat then place; target object is held; microwave is open; goal requires heating the object.

### skill_015: Failure Lesson

**Description:** Repeatedly using 'use microwave' or 'heat object with microwave' while the object is inside the microwave can fail without changing state.

**Why It Happens:** The environment may require the object to be held or the microwave to be open for the heat action to succeed.

**How To Avoid:** If heating fails, take the object out, ensure the microwave is open, and try the direct heat action while holding the object.

### skill_016: Failure Lesson

**Description:** After a successful direct heat while holding the object, the object remains in inventory; attempting to take it from the microwave returns 'Nothing happens'.

**Why It Happens:** The direct heat action does not place the object inside the microwave, so there is nothing to take out.

**How To Avoid:** After heating, verify with inventory that the object is still held and proceed directly to the destination; do not attempt to take it from the microwave.

### skill_017: Place heated object at destination before finishing

**Principle:** After heating and confirming the object is held, go to the destination, open it if closed, and put the object there. Heating alone is an intermediate milestone, not task completion; do not declare HANDOFF until the object is placed.

**When To Apply:** Task type heat then place; object is heated and held; destination is known.

## Operation Worker — Cool then place

### skill_018: Cool held object with open fridge

**Principle:** When the goal requires a cooled object, first acquire the object, then navigate to an open fridge while holding it, and use the cool command with the fridge.

**When To Apply:** Holding the target object and standing at an open fridge, with the goal requiring the object to be cool.

### skill_019: Failure Lesson

**Description:** Placing an object inside a fridge does not cool it; the cool command must be used while holding the object at the fridge.

**Why It Happens:** The environment only changes an object's temperature through the explicit cool action, not through containment.

**How To Avoid:** After reaching the fridge with the object in hand, issue 'cool <object> with fridge' instead of putting the object into the fridge.

### skill_020: Failure Lesson

**Description:** A put action fails silently if the destination is closed or the agent is not at the destination; open the destination and navigate to it before placing.

**Why It Happens:** The environment requires the agent to be at an open receptacle to place an object.

**How To Avoid:** After cooling, go to the destination, open it if closed, then put the held object there.

### skill_021: Failure Lesson

**Description:** Cooling the object is not sufficient; the task is complete only after the cooled object is placed at the required destination.

**Why It Happens:** The mission goal includes both cooling and placing, so declaring handoff after cooling alone leaves the task incomplete.

**How To Avoid:** After cooling, continue to the destination and place the object before declaring success.

## Operation Worker — Place two objects

### skill_022: Two-item placement: place both objects before handoff

**Principle:** For tasks requiring two same-type objects at a destination, pick up one object, carry it to the destination, place it, then search for a second distinct instance and repeat. Track a placed count and only declare HANDOFF after both objects are at the destination; do not re-take an already-placed object.

**When To Apply:** When the goal is to put two objects of the same type at a target location and the agent cannot hold both simultaneously.
