import pyttsx3
engine = pyttsx3.init() # object creation
# VOICE
voices = engine.getProperty('voices')       # getting details of current voice
engine.setProperty('voice', voices[1].id)  # changing index, changes voices. o for male
# engine.setProperty('voice', voices[1].id)  
engine.say("Hello sherlock sampath!")
# engine.say('My current speaking rate is ' + str(rate))
engine.runAndWait()
engine.stop()



voices = engine.getProperty('voices')       # getting details of current voice
engine.setProperty('voice', voices[0].id) 