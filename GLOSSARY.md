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
The event of a Track's centroid moving from one side of a Tripwire to the other, past the hysteresis margin. Directional: counted as IN or OUT.
_Avoid_: Pass, entry/exit (reserve those for the counted direction, not the event)

**Storefront**:
A named Tripwire with its own color and independent IN/OUT tally, used when one scene has several entrances.
_Avoid_: Entrance, door, zone

**Net occupancy**:
The running difference total IN minus total OUT: an estimate of how many Persons are currently inside.
_Avoid_: Headcount, capacity, footfall

## Deferred (not yet modeled)

**Customer**:
A future refinement of Person that would distinguish shoppers from passersby and staff. Explicitly out of scope today; the system counts Persons, not Customers.
