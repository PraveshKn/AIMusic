import os
import json
import numpy as np
import music21 as m21
import tensorflow as tf

STATIC_PATH = 'static/models'
MODEL_NAME = 'music_model.h5'
ITN_PATH = 'int_notes.json'
ITD_PATH = 'int_durations.json'
def sample_with_temp(preds, temperature):
    '''
    Deviate from model dataset
    '''
    if temperature == 0:
        return np.argmax(preds)
    else:
        preds = np.log(preds) / temperature
        exp_preds = np.exp(preds)
        preds = exp_preds / np.sum(exp_preds)
        return np.random.choice(len(preds), p=preds)

def load_decoder(file1, file2):
    # load json file
    with open(file1) as file1:
        element_to_int = json.load(file1)
    with open(file2) as f:
        int_to_element = json.load(f)
    return element_to_int, int_to_element

def fraction(duration):
    '''
    Args:
        duration: str -> duration in string
    Return
        duration: float -> changing str to float
    '''
    if '/' in duration:
        lst = duration.split('/')
        return int(lst[0])/int(lst[1])
    else:
        return float(duration)


def music_stream(instrument, model_input, timesig, bpm, notes_seed=None, durations_seed=None):
    model_dir = os.path.join(STATIC_PATH, model_input, MODEL_NAME)
    itn_dir = os.path.join(STATIC_PATH, model_input, ITN_PATH)
    itd_dir = os.path.join(STATIC_PATH, model_input, ITD_PATH)
    # assigning seq_len for model accordingly as used while training
    if model_input == "hindi":
        max_seq_len = 32
        seq_len = 32
        max_extra_notes = 175
    else:
        max_seq_len = 16
        seq_len = 16
        max_extra_notes = 128

    model = tf.keras.models.load_model(model_dir)

    # getting decoder dict
    int_to_note, int_to_duration = load_decoder(itn_dir, itd_dir)

    # parsing json file
    int_to_note = json.loads(int_to_note)
    int_to_duration = json.loads(int_to_duration)

    # find range upto which
    n_notes_distict = len(int_to_note)
    n_durations_distinct = len(int_to_duration)

    notes_temp = 0.5
    duration_temp = 0.5

    if notes_seed is None:
        # randomize seed for predictation
        notes = np.random.randint(n_notes_distict, size=seq_len).tolist()
        durations = np.random.randint(n_durations_distinct, size=seq_len).tolist()
    else:
        notes = notes_seed
        durations = durations_seed

    notes_input_sequence = notes
    durations_input_sequence = durations

    prediction_output = []
    overall_preds = []

    for note_index in range(max_extra_notes):
        prediction_input = [
            np.array([notes_input_sequence]), 
            np.array([durations_input_sequence])
        ]

        notes_prediction, durations_prediction = model.predict(
            prediction_input, verbose=0)
        new_note = np.zeros(128)

        for idx, n_i in enumerate(notes_prediction[0]):
            try:
                note_name = int_to_note[str(idx)]
                midi_note = m21.note.Note(note_name)
                new_note[midi_note.pitch.midi] = n_i
            except:
                pass

        overall_preds.append(new_note)

        i1 = sample_with_temp(notes_prediction[0], notes_temp)
        i2 = sample_with_temp(durations_prediction[0], duration_temp)

        note_result = int_to_note[str(i1)]
        duration_result = fraction(int_to_duration[str(i2)])

        prediction_output.append([note_result, duration_result])

        notes_input_sequence.append(i1)
        durations_input_sequence.append(i2)

        if len(notes_input_sequence) > max_seq_len:
            notes_input_sequence = notes_input_sequence[1:]
            durations_input_sequence = durations_input_sequence[1:]

    overall_preds = np.transpose(np.array(overall_preds))

    midi_stream = m21.stream.Stream()

    instrument_func = getattr(m21.instrument, instrument)()
    midi_stream.insert(0.0, instrument_func)

    new_bpm = int(bpm)
    time_signature = m21.meter.TimeSignature(timesig)
    bits_per_minute = m21.tempo.MetronomeMark(number=new_bpm)
    midi_stream.append(time_signature)
    midi_stream.append(bits_per_minute)

    # create note and chord objects based on the values generated by the model
    for pattern in prediction_output:
        note_pattern, duration_pattern = pattern
        # pattern is a chord
        if ('.' in note_pattern):
            notes_in_chord = note_pattern.split('.')
            chord_notes = []
            for current_note in notes_in_chord:
                new_note = m21.note.Note(current_note)
                new_note.duration = m21.duration.Duration(
                    quarterLength=duration_pattern)
                chord_notes.append(new_note)
            new_chord = m21.chord.Chord(chord_notes)
            # midi_stream.append(tsThreeFour)
            midi_stream.append(new_chord)
        elif note_pattern == 'rest':
            # pattern is a rest
            new_note = m21.note.Rest()
            new_note.duration = m21.duration.Duration(
                quarterLength=duration_pattern)
            midi_stream.append(new_note)
        else:
            # pattern is a note
            new_note = m21.note.Note(note_pattern)
            new_note.duration = m21.duration.Duration(
                quarterLength=duration_pattern)
            midi_stream.append(new_note)
    return midi_stream
