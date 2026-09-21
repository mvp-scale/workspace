window.MockApollo = {
 "id": "apollo",
 "kind": "real",
 "title": "Apollo 13, air-to-ground and flight loop (real transcript)",
 "blurb": "Real NASA transcript, public domain (source: NASA Apollo Flight Journal). Speakers and words are original. The tags on it are MOCK annotations: scripted for layout, not model output. Turns 8 and 23 match the two documented events in the scene file.",
 "source": "https://www.nasa.gov/history/afj/ap13fj/08day3-problem.html",
 "turns": [
  {
   "speaker": "Swigert",
   "text": "Okay, Houston..."
  },
  {
   "speaker": "Lovell",
   "text": "...Houston..."
  },
  {
   "speaker": "Swigert",
   "text": "...we've had a problem here. [Pause.]"
  },
  {
   "speaker": "Fenner (GUIDO)",
   "text": "FLIGHT, GUIDANCE."
  },
  {
   "speaker": "Kranz (FLIGHT)",
   "text": "Go GUIDANCE."
  },
  {
   "speaker": "Lousma",
   "text": "This is Houston. Say again, please."
  },
  {
   "speaker": "Fenner (GUIDO)",
   "text": "We've had a Hardware Restart. I don't know what it was."
  },
  {
   "speaker": "Kranz (FLIGHT)",
   "text": "Okay. GNC, you want to take a look at it? See if you see any problems?"
  },
  {
   "speaker": "Lovell",
   "text": "[Garble.] Ah, Houston, we've had a problem. We've had a Main B Bus Undervolt."
  },
  {
   "speaker": "Kranz (FLIGHT)",
   "text": "Roger, we're copying it, CapCom. We see a hardware restart."
  },
  {
   "speaker": "Kranz (FLIGHT)",
   "text": "You see an AC Bus Undervolt there, GUIDANCE - ehhhm EECOM?"
  },
  {
   "speaker": "Lousma",
   "text": "Roger. Main B Undervolt. [Long pause.]"
  },
  {
   "speaker": "Liebergot (EECOM)",
   "text": "Negative, FLIGHT"
  },
  {
   "speaker": "Kranz (FLIGHT)",
   "text": "I believe the crew reported it."
  },
  {
   "speaker": "Lousma (CAPCOM)",
   "text": "We've got a Main Bus B undervolt."
  },
  {
   "speaker": "Liebergot (EECOM)",
   "text": "Okay, flight, we've got some instrumentation funnies. Let me add them up."
  },
  {
   "speaker": "Kranz (FLIGHT)",
   "text": "Roger."
  },
  {
   "speaker": "Lousma",
   "text": "Okay, stand by, 13. We're looking at it. [Pause.]"
  },
  {
   "speaker": "Liebergot (EECOM)",
   "text": "We may have had an instrumentation problem, FLIGHT."
  },
  {
   "speaker": "Kranz (FLIGHT)",
   "text": "Rog."
  },
  {
   "speaker": "Glines (INCO)",
   "text": "FLIGHT, INCO."
  },
  {
   "speaker": "Kranz (FLIGHT)",
   "text": "Go, INCO."
  },
  {
   "speaker": "Glines (INCO)",
   "text": "We switched to wide beam width about the time he had that problem."
  },
  {
   "speaker": "Haise",
   "text": "Okay. Right now, Houston, the voltage is - is looking good. And we had a pretty large bang associated with the Caution and Warning there. And as I recall, Main B was the one that had had an amp spike on it once before. [Pause.]"
  },
  {
   "speaker": "Lousma",
   "text": "Roger, Fred. [Long pause.]"
  }
 ],
 "watch": [
  {
   "code": "RPT",
   "label": "Incident report",
   "prompt": "Someone reports something has gone wrong",
   "hue": 18
  },
  {
   "code": "UNC",
   "label": "Uncertainty",
   "prompt": "The speaker is unsure or guessing what happened",
   "hue": 48
  },
  {
   "code": "TEC",
   "label": "Technical fault",
   "prompt": "A specific equipment fault is named",
   "hue": 205
  },
  {
   "code": "URG",
   "label": "Urgency",
   "prompt": "Something sounds urgent or dangerous",
   "hue": 350
  },
  {
   "code": "HST",
   "label": "Prior history",
   "prompt": "The speaker refers to an earlier occurrence",
   "hue": 275
  }
 ],
 "marks": [
  {
   "turn": 2,
   "phrase": "we've had a problem",
   "code": "RPT",
   "p": 0.93,
   "note": "First report of trouble, calm wording"
  },
  {
   "turn": 6,
   "phrase": "I don't know what it was",
   "code": "UNC",
   "p": 0.88,
   "note": "Cause unknown to the speaker"
  },
  {
   "turn": 8,
   "phrase": "Main B Bus Undervolt",
   "code": "TEC",
   "p": 0.91,
   "note": "Named fault: Main B bus undervolt",
   "fact": [
    "Fault",
    "Main B bus undervolt"
   ]
  },
  {
   "turn": 8,
   "phrase": "we've had a problem",
   "code": "RPT",
   "p": 0.9,
   "note": "Documented event: Lovell's report"
  },
  {
   "turn": 18,
   "phrase": "We may have had an instrumentation problem",
   "code": "UNC",
   "p": 0.79,
   "note": "Framed as a possible sensor error"
  },
  {
   "turn": 23,
   "phrase": "pretty large bang",
   "code": "URG",
   "p": 0.86,
   "note": "Documented event: crew report a real bang",
   "fact": [
    "Physical sign",
    "Large bang with Caution and Warning"
   ]
  },
  {
   "turn": 23,
   "phrase": "amp spike on it once before",
   "code": "HST",
   "p": 0.82,
   "note": "Main B had an amp spike earlier"
  }
 ]
};
