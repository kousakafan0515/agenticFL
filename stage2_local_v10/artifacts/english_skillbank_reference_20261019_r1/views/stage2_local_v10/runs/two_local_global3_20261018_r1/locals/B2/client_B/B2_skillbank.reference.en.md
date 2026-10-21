# English reference: B2_skillbank.json

Display only. Original IDs, buckets, and source references are preserved. This file was not used in any run.

## Executor — General

### skill_001: First locate the target object, then locate the target container.

**Principle:** For pick-and-place tasks, first search for and obtain the target object, then go to the target container to execute placement.

**When To Apply:** When the task requires placing an object on a container/furniture and the initial location is unknown.

### skill_002: Must be at the target container before placing.

**Principle:** Before executing put, you must have already reached the target container/furniture location via go to; otherwise put may be ineffective.

**When To Apply:** When the target object has been obtained and you are ready to place it.

### skill_003: Prioritize checking common support surfaces, then check closed containers.

**Principle:** When searching for the target object, prioritize checking open support surfaces such as tables, countertops, shelves, beds, sofas, etc.; if not found, then check closed containers such as drawers, cabinets, etc.

**When To Apply:** When the target object's initial location is unknown and the room contains multiple types of furniture/containers.

### skill_004: Avoid invalid examine and blind exhaustive search

**Principle:** Do not use examine as a search action; if many containers have been checked and the target still has not been found, reassess visible support surfaces or whether the target exists, rather than continuing blind exhaustive search.

**When To Apply:** When searching for the target object fails or the target has not been found for a long time.

### skill_005: Avoid repeating invalid actions

**Principle:** When an action returns "Nothing happens", do not repeat the same action; change the state (such as opening/closing a container, moving location, taking out an object) and then retry. If `go to <location>` returns "Nothing happens", treat that location as unreachable and switch to another candidate location; if `open` returns "Nothing happens", the container may already be open, so directly continue put.

**When To Apply:** When any action returns "Nothing happens" and does not change the environment state.

### skill_006: Avoid declaring completion before success is confirmed

**Principle:** Do not output a completion state or stop acting until environmental observation confirms the final placement action succeeded; stop immediately after success and do not issue inventory or empty actions again. If the final put returns "Nothing happens", first confirm that the target location has been reached and then retry, rather than prematurely declaring completion or failure.

**When To Apply:** After executing the final placement action.

## Executor — Examine with desk lamp

### skill_007: Desklamp observation task execution flow

**Principle:** For tasks of the “examine/look at X with/under the desklamp” type, first locate the target object and the desklamp; if the target is portable, pick up the target, move to the desklamp's location, then use the desklamp (use desklamp <id>) to complete the observation. If the target object is already on the furniture where the desklamp is, pick up the target object first and then use the desklamp; if the first table has no desklamp, continue searching other support surfaces (sidetable, shelf, dresser) while keeping the target object held.

**When To Apply:** When the task goal is to observe the relationship between an object and the desklamp (examine X with desklamp or look at X under desklamp).

### skill_008: Failure Lesson

**Description:** In desklamp observation tasks, do not use the `examine X with desklamp` action; this action usually returns "Nothing happens"; instead, pick up the target object and then use `use desklamp`.

**Why It Happens:** The ALFWorld environment does not support passing the desklamp as a tool parameter to the examine action; the desklamp is a fixed object and can only be turned on via the use action.

**How To Avoid:** If you need to observe the relationship between the object and the desk lamp, first ensure the target object is in hand or nearby, then execute `use desklamp` to turn on the desk lamp, rather than `examine X with desklamp`.

### skill_009: Failure Lesson

**Description:** The desk lamp is an object fixed on a desk or side table, not a navigable location; executing `go to desklamp 1` will return "Nothing happens"; you should directly use `use desklamp` at the current location of the desk lamp.

**Why It Happens:** In ALFWorld, only furniture and containers can be navigation targets; small objects such as desk lamps cannot be targets for go to.

**How To Avoid:** When already at the furniture location where the desk lamp is, directly execute `use desklamp`; do not attempt `go to desklamp`.

### skill_010: Failure Lesson

**Description:** The desk lamp is a fixed object and cannot be picked up; executing `take desklamp 1` will return "Nothing happens"; instead, bring the target object to the desk lamp or directly use the desk lamp.

**Why It Happens:** In ALFWorld, desk lamps are marked as fixed objects and cannot be carried.

**How To Avoid:** Do not attempt to pick up the desk lamp; if the target object is carryable, pick up the target object and move to the location of the desk lamp, then use the desk lamp.

## Executor — Clean then place

### skill_011: Clean-then-place execution loop

**Principle:** For clean-then-place goals, execute a stable loop: locate the exact target object named in the goal (do not substitute a similar object such as butterknife for knife or pan for pot), take it, go to a sinkbasin or bathtubbasin, clean it, then go to the destination receptacle, open it if closed, and put the object in/on it. If the destination already contains a similar object, still take the correct object, clean it, and place it back rather than swapping.

**When To Apply:** Use when the goal is to put a clean object into a specified receptacle and the object is not already clean.

### skill_012: Failure Lesson

**Description:** A clean action can fail with 'Nothing happens' if the agent is not at the sinkbasin or bathtubbasin. If cleaning fails, go to the cleaning receptacle and retry the clean action.

**Why It Happens:** The environment requires the agent to be co-located with the cleaning fixture before the clean action is valid.

**How To Avoid:** After taking the object, explicitly go to sinkbasin 1 or bathtubbasin 1, then issue clean <object> with <fixture>.

### skill_013: Failure Lesson

**Description:** If the destination receptacle is closed, open it before attempting to put the clean object in/on it.

**Why It Happens:** Closed containers such as drawers, cabinets, fridges, and microwaves must be opened before items can be placed inside.

**How To Avoid:** When arriving at the destination, check whether it is closed; if so, issue open <receptacle>, then put <object> in/on <receptacle>.

## Executor — Heat then place

### skill_014: Heat held object with microwave

**Principle:** For heat-and-place tasks, after locating the target object and the microwave, take the object, go to the microwave, open it if closed, then execute `heat <object> with microwave 1` while holding the object. If the first heat attempt returns 'Nothing happens', take the object out of the microwave and retry `heat <object> with microwave 1` while holding it. Do not attempt to heat using non-microwave appliances (stoveburner, toaster, coffeemachine); these return 'Nothing happens'.

**When To Apply:** When the goal requires heating an object and a microwave is available, especially if initial heat attempts fail while the object is inside or on the microwave.

### skill_015: Do not assume heating succeeded without confirmation

**Principle:** Only proceed to the placement step after an observation explicitly confirms heating, such as 'You heat the <object> using the microwave 1.' If heating has not been confirmed, continue trying valid heating methods rather than placing the object.

**When To Apply:** After attempting to heat an object and before placing it at the destination.

### skill_016: Move to destination before placing heated object

**Principle:** After successfully heating the object, go to the target receptacle/location, open it if needed, and then execute `put <object> in/on <destination>`. If the put action returns 'Nothing happens', verify current location and move to the destination before retrying.

**When To Apply:** When the object is hot and the goal requires placing it in or on a specific location.

## Executor — Cool then place

### skill_017: Cooling requires an open fridge and direct cool action

**Principle:** To cool an object, first go to the fridge and open it, then use the cool action with the fridge while holding the object; do not rely on putting the object into the fridge and taking it out as a substitute for cooling. A cool attempt while not co-located with an open fridge returns 'Nothing happens'.

**When To Apply:** When the task requires cooling an object and a fridge is available.

### skill_018: Do not assume a cool object is already in the fridge

**Principle:** If the task requires a cool object, verify the object is actually cooled by using the cool action; merely finding an object in the fridge does not guarantee it is cool, and taking it out without cooling may fail the task.

**When To Apply:** When searching for a cool object and finding a candidate inside the fridge.

### skill_019: Search efficiently by opening containers and tracking visited locations

**Principle:** When the target object is not in the first few locations, systematically open and check cabinets, drawers, countertops, and other receptacles, keeping track of which have been checked to avoid redundant loops.

**When To Apply:** When the target object is not immediately found and many storage locations exist.

## Executor — Place two objects

### skill_020: Dual-item placement: first take the first item and temporarily store it, then take the second item and perform the final placement.

**Principle:** In two-object placement tasks, if only one object can be carried at a time, first find and pick up the first target object; if the target container is reachable, place it directly into the final target container; otherwise temporarily store it on a safe open support surface, then find and pick up the second target object, and finally place both objects into the target container. Prefer searching open support surfaces (table, countertop, shelf, sofa); the two objects are often on the same support surface.

**When To Apply:** When the task requires putting two items of the same type into the same target container, and the environment restricts carrying to one item at a time.

### skill_021: Failure Lesson

**Description:** In dual-item placement tasks, if you already hold one item, directly attempting to take the second item of the same type usually fails and returns "Nothing happens".

**Why It Happens:** The environment restricts carrying to one item at a time, so you must first put down or temporarily store the current item before you can take the second item.

**How To Avoid:** Before taking the second item, first put the first item into the target container or a temporary container to ensure the inventory is empty.

### skill_022: Failure Lesson

**Description:** In dual-item placement tasks, putting an item into a non-target container such as garbagecan may cause it to be irretrievable later or cause the task to fail.

**Why It Happens:** Some containers may not accept items, or the item's state may change after being put in, making it impossible to continue completing the task.

**How To Avoid:** Prioritize placing temporarily held items into the final target container; if temporary storage is necessary, choose a container from which they can be retrieved normally, and avoid using containers such as garbagecan that may be irreversible.

## Critic — General

### skill_001: Search visible surfaces before opening closed containers

**Principle:** For object-location tasks, first scan visible surfaces (tables, dressers, beds, countertops, shelves) for the target object before opening drawers, cabinets, or other closed containers.

**When To Apply:** At the start of a task when the target object has not yet been located.

### skill_002: Open closed containers before inspecting or taking

**Principle:** When a drawer, cabinet, fridge, microwave, or other closed container may hold the target object, open it before attempting to inspect or take an item from it; closed containers cannot be searched directly.

**When To Apply:** When the target object may be inside a closed drawer, cabinet, safe, fridge, or microwave.

### skill_003: After picking up the target, go directly to the destination and put it there

**Principle:** Once the target object is held, navigate to the specified destination receptacle and execute the put action without unnecessary intermediate steps.

**When To Apply:** Immediately after successfully taking the target object.

### skill_004: Failure Lesson

**Description:** If an action returns 'Nothing happens', do not repeat the same invalid command; verify the current location and choose a valid reachable receptacle or action instead. This applies to moves, opens, takes, and examines alike.

**Why It Happens:** The agent may issue commands for locations or objects that are not currently accessible or valid, or use a bare object name instead of the exact identifier, causing no state change.

**How To Avoid:** After a 'Nothing happens' observation, re-check the current location and available objects, confirm exact object identifiers from the observation, then select a different valid action rather than retrying the same command.

### skill_011: Failure Lesson

**Description:** Several failed or budget-exhausted episodes show the Executor repeatedly moving to invalid or already-searched locations, or arriving at closed receptacles without opening them. This wastes steps and prevents finding the target object.

**Why It Happens:** The environment may return 'Nothing happens' for invalid moves, and the Executor may loop on the same location or command without updating its search strategy.

**How To Avoid:** Track visited receptacles and their contents. If a move returns 'Nothing happens', do not repeat it; verify the current location and choose a different unsearched receptacle. Open closed receptacles before checking them. Prioritize likely object locations based on object type.

## Critic — Examine with desk lamp

### skill_005: Desklamp observation task: first locate and carry the target object, then turn on the desklamp at the desklamp location.

**Principle:** For goals of the type “examine/look at X with/under the desklamp”, first find the target object and take it in hand, then move to the desklamp’s location, and finally turn on the desklamp to complete the observation.

**When To Apply:** When the goal requires observing something with the desklamp, and the target object is not at the desklamp’s location.

### skill_006: Desklamp observation task: when the target object and the desklamp are in the same place, directly turn on the desklamp.

**Principle:** If the target object and the desklamp are already in the same location, directly use the desklamp to complete the observation; there is no need to first take the target object.

**When To Apply:** After arriving at the desklamp’s location, observe that the target object is also on the same surface or in the same container.

### skill_007: Failure Lesson

**Description:** The desklamp is a fixed object; take desklamp returns “Nothing happens”, wasting steps.

**Why It Happens:** The environment models the desklamp as a fixed device that cannot be carried.

**How To Avoid:** Do not execute take desklamp; instead move to the desklamp’s location and directly use desklamp.

### skill_008: Failure Lesson

**Description:** If 'use desklamp' returns 'Nothing happens', the agent is likely not at the desklamp's location; the Critic should advise verifying position and navigating to the desklamp before retrying, rather than repeating the same command.

**Why It Happens:** The use action requires the agent to be co-located with the desklamp; issuing it from elsewhere produces no state change.

**How To Avoid:** After a failed use desklamp, advise checking current location and moving to the desklamp, then using it. Do not repeat the same command from the same spot.

## Critic — Clean then place

### skill_009: Clean-then-place workflow for placing after cleaning.

**Principle:** For tasks of the form 'put a clean X in/on Y', first locate X, take it, go to a sinkbasin, clean X with the sinkbasin, then go to the target receptacle Y and put X in/on Y.

**When To Apply:** When the goal explicitly requires an object to be clean before placement, such as 'put a clean dishsponge in drawer', 'put a clean cup in shelf', or 'clean some egg and put it in diningtable'.

### skill_010: Failure Lesson

**Description:** Cleaning attempts can fail with 'Nothing happens' when the Executor is not at a valid sinkbasin or is not holding the object. The Critic should advise verifying both conditions before retrying, and try a different sinkbasin if needed.

**Why It Happens:** The clean action requires the agent to be at a valid cleaning receptacle, typically a sinkbasin, while holding the object; some receptacles do not support cleaning for certain objects.

**How To Avoid:** Advise: hold the object, go to a sinkbasin, then clean. If cleaning returns 'Nothing happens', verify the current location and try a different sinkbasin. Do not repeatedly attempt the same invalid clean action.

## Critic — Heat then place

### skill_012: Heat held object by placing it in an open microwave, then heating

**Principle:** For heat-then-place tasks, first navigate to the microwave, open it, put the held object inside, and then issue the heat command.

**When To Apply:** When the goal requires heating an object and the object is currently held in inventory.

### skill_013: Failure Lesson

**Description:** Heating an object directly from inventory fails with 'Nothing happens'; success requires putting the object into the open microwave, then heating. The Critic must not declare the object heated while it is merely held.

**Why It Happens:** The heating action requires the target object to be inside the microwave, not in the agent's inventory; the Critic may misread a failed heat as success.

**How To Avoid:** Advise: go to microwave, open it, put the object inside, then heat. Verify the observation text before declaring success; do not claim an item was heated while in inventory.

### skill_014: Failure Lesson

**Description:** Recommending unsupported heating appliances such as stoveburners or toasters after a microwave failure leads to 'Nothing happens'; the reliable path is the open microwave with put-then-heat.

**Why It Happens:** The environment may not support heating on stoveburners or toasters for the target object, and occupied stoveburners cannot accept another object.

**How To Avoid:** Do not advise stoveburner or toaster heating as a recovery. Direct the Executor back to the open microwave: put the object inside, then heat.

## Critic — Cool then place

### skill_015: Cool held item at an open fridge, then go straight to destination

**Principle:** To cool an item, hold it, navigate to the fridge, open the fridge, and issue the cool command on the held item; after a confirmed cool, go directly to the destination receptacle and put the item there without retrieving it from the fridge.

**When To Apply:** When the goal requires a cooled item and the agent is holding the target object.

### skill_016: Failure Lesson

**Description:** Advising the Executor to put the item into the open fridge before cooling is wrong; in successful cooling episodes the Executor holds the item, opens the fridge, and issues 'cool X with fridge' directly, keeping the item in inventory.

**Why It Happens:** The cooling mechanic works on a held item when the agent is at an open fridge; the item does not need to be placed inside and retrieved.

**How To Avoid:** Advise: go to fridge, open fridge, cool the held item directly, then go to the destination and put it there. Do not instruct put-into-fridge-then-take.

## Critic — Place two objects

### skill_017: Two-item placement: first place the first item, then take the second item.

**Principle:** In a two-object placement task, after finding the first target object, first place it in the target container, then find and retrieve the second target object.

**When To Apply:** When the task requires placing two objects of the same type into the same target container, and the first object has already been found and picked up.

### skill_018: Failure Lesson

**Description:** In dual-item placement, issuing a put action before arriving at the destination receptacle returns 'Nothing happens'; the Critic should confirm arrival before advising put.

**Why It Happens:** The put action requires the agent to be co-located with the target container; putting from a distance cannot take effect.

**How To Avoid:** Before advising put, confirm the Executor has navigated to the destination receptacle; if a put fails, advise moving to the destination and retrying there.

### skill_019: Failure Lesson

**Description:** In dual-item placement, attempting to take the second item while already holding the first returns 'Nothing happens'; the Critic should advise placing the held item in the destination first to free the hands.

**Why It Happens:** The agent can typically hold only one item at a time, so a take while holding fails.

**How To Avoid:** Before advising the take of the second item, direct the Executor to put the first item into the destination receptacle, then return for the second.

### skill_020: Failure Lesson

**Description:** In a two-object placement task, if multiple containers have been opened but the target object has not been found, prioritize checking opened containers and visible surfaces (such as countertops and shelves), and avoid repeatedly visiting locations already confirmed to contain no target object.

**Why It Happens:** Repeatedly visiting already checked locations wastes the action budget, causing the task to fail when the budget is exhausted.

**How To Avoid:** Maintain a list of checked locations and prioritize checking unchecked opened containers and visible surfaces; if the target object is on a visible surface, pick it up directly.
