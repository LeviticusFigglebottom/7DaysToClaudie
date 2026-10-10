extends GutTest
## Sound captions (mid-game audit G4): a big unseen sound is captioned once per group per its
## interval, and not when it is right beside the player (seen, not just heard).


func test_one_caption_per_group_per_interval() -> void:
	if not Events.has_signal(&"sound_caption"):
		pending("Events.sound_caption not on this branch yet")
		return
	watch_signals(Events)
	var at := Vector3(500, 0, 500)
	SoundCaptions.say("test:wolves:a", "wolves howling", at, 10.0)
	SoundCaptions.say("test:wolves:a", "wolves howling", at, 10.0)
	assert_signal_emit_count(Events, "sound_caption", 1, "the same pack again at once is not captioned")
	SoundCaptions.say("test:wolves:b", "wolves howling", at, 10.0)
	assert_signal_emit_count(Events, "sound_caption", 2, "another pack is")


func test_cells_group_the_hollowed_calling() -> void:
	assert_eq(SoundCaptions.cell_key("hollowed", Vector3(5, 0, 5)), SoundCaptions.cell_key("hollowed", Vector3(30, 0, 12)))
	assert_ne(SoundCaptions.cell_key("hollowed", Vector3(5, 0, 5)), SoundCaptions.cell_key("hollowed", Vector3(45, 0, 5)))
