"""Route pipe events to the selected player without mixing score histories."""


def accepts_pipe_event(data, player_mode):
    if not isinstance(data, dict):
        return False
    source = data.get("source")
    if player_mode == "bmz":
        return source == "bmz-player"
    if player_mode == "beatoraja":
        # Endless Dream's original payloads do not carry a source field.
        return source in (None, "beatoraja", "lr2oraja-endlessdream")
    return False
