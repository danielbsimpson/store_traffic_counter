# Store Traffic Counter

A proof-of-concept computer-vision pipeline that detects people in video, tracks them across frames, and tallies how many cross a configured line. Built as a portfolio demonstration.

## Language

**Person**:
The canonical entity the system detects and counts: any human the detector finds in a frame. The system makes no claim about intent or role.
_Avoid_: Customer, shopper, pedestrian, visitor

**Track**:
A single Person followed across consecutive frames under one stable ID, from first detection until it disappears past the timeout.
_Avoid_: Trajectory, path

**Tripwire**:
A configured line segment (horizontal or angled) whose crossing is counted. Has a direction that defines which side is IN and which is OUT.
_Avoid_: Gate, boundary, threshold

**Crossing**:
The event of a Track moving from one side of a Tripwire to the other, past the hysteresis margin. Counted as IN or OUT, but not in itself proof of physical passage into or out of a store.
_Avoid_: Confirmed entry, confirmed exit

**Storefront**:
A named Tripwire with its own color and independent IN/OUT tally, used when one scene has several entrances.
_Avoid_: Entrance, door, zone

**Net occupancy**:
The running difference total IN minus total OUT: an estimate of how many Persons are currently inside.
_Avoid_: Headcount, capacity, footfall

### Doorway passage

**Entry**:
A Person passing from outside a store to inside it through a Doorway. Approaching the Doorway or returning outside without going inside is not an Entry.
_Avoid_: Approach

**Exit**:
A Person passing from inside a store to outside it through a Doorway. A Person who enters and then immediately leaves makes one Entry and one Exit.
_Avoid_: Departure from an approach

**Unresolved passage**:
A possible Entry or Exit for which the available observations do not establish whether the Person passed between outside and inside. It is neither a confirmed passage nor evidence that no passage occurred.

**Doorway**:
A specific physical opening connecting the outside to the inside of one store, with an inside and an outside side. A store may have several Doorways; a shared arcade entrance is not a Doorway into an individual tenant's store.
_Avoid_: Approach region, storefront

**Directional motion**:
The direction and rate of a Person's movement relative to a Doorway. It is evidence about a possible passage, not an Entry or Exit in itself.
_Avoid_: Momentum

## Deferred (not yet modeled)

**Customer**:
A future refinement of Person that would distinguish shoppers from passersby and staff. Explicitly out of scope today; the system counts Persons, not Customers.
