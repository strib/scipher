#!/usr/bin/env python

import itertools
import random

# generate all orders of sections

sections = ["CFP_TOPIC_SECTION",
            "KEYNOTE_SECTION",
            "ORGS_SECTION",
            "PC_SECTION",
            "STEER_SECTION",
            "DATE_SECTION",
            "LOC_SECTION"]

# We only want ~1000 bodies, if we take all of them it takes too long to load
first = True
for i in range(len(sections), 4, -1):
    for p in itertools.permutations(sections, i):
        if random.randint(0,30) > 0 and not first:
            continue
        first = False
        print ("CFP_BODY -> CFP_INTRO_SECTION SPACE_NEWLINE CFP_SCOPE_SECTION "
               "SPACE_NEWLINE %s SPACE_NEWLINE CFP_SUBMIT_SECTION" %
               " SPACE_NEWLINE ".join(p))
        print ("CFP_BODY -> CFP_SCOPE_SECTION SPACE_NEWLINE %s "
               "SPACE_NEWLINE CFP_SUBMIT_SECTION" % " SPACE_NEWLINE ".join(p))
        print ("CFP_BODY -> CFP_INTRO_SECTION SPACE_NEWLINE %s SPACE_NEWLINE "
               "CFP_SCOPE_SECTION SPACE_NEWLINE CFP_SUBMIT_SECTION" %
               " SPACE_NEWLINE ".join(p))

