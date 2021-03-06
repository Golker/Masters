import math
from collections import OrderedDict
import mido
from mido import midifiles

from helpers import get_timber_group
from percussion_devices import PercussionDevicesEnum

# coding=utf-8

__author__ = 'Luca'


class MidiProcessor(object):
    """
        Class that performs the whole MIDI processing.
    """

    def __init__(self, midi_file_path, runtime):
        self.mid = mido.midifiles.MidiFile(midi_file_path)
        self.filename = midi_file_path.split('/')[-1]
        self.runtime = runtime
        self.ticks_per_beat = self.mid.ticks_per_beat
        # self.mid.print_tracks()
        self.beats = {}
        self.instruments = {}
        self.ordered_beats = {}
        self.numerator, self.denominator = 4, 4
        self.tempo, self.abs_time_counter, self.max_track_len = 0, 0, 0
        self.bar_size, self.bar_counter, self.bpm = 0, 0, 0

    def process_tracks(self):
        for i, track in enumerate(self.mid.tracks):
            self.abs_time_counter = 0
            for j, message in enumerate(track):
                # not only 'note_on' messages have times greater than zero
                self.abs_time_counter += message.time
                if message.type == 'note_on':
                    if message.velocity > 0 and message.channel == 9:
                        # The same absolute time might have beats from
                        # multiple instruments. Therefore, a list is required.
                        if self.abs_time_counter not in self.beats:
                            self.beats[self.abs_time_counter] = [message]
                        else:
                            # Check if there are no other messages from the same 
                            # instrument at that same time before inserting
                            notes = list(filter(
                                lambda b: b.note == message.note, self.beats[self.abs_time_counter]
                            ))
                            if not len(notes):
                                self.beats[self.abs_time_counter].append(message)
                elif message.type == 'set_tempo':
                    self.tempo = message.tempo
                    self.bpm = (1000000 / self.tempo) * 60
                elif message.type == 'time_signature':
                    self.numerator = message.numerator
                    self.denominator = message.denominator
            if self.abs_time_counter > self.max_track_len:
                self.max_track_len = self.abs_time_counter

    def setup_variables(self):
        self.ordered_beats = OrderedDict(sorted(self.beats.items()))

    def beats_by_instrument(self):
        for abs_beat_time, instruments_list in self.ordered_beats.items():
            for single_instrument in instruments_list:
                instrument_name = str(single_instrument.note)
                if instrument_name not in self.instruments:
                    self.instruments[instrument_name] = []
                self.instruments[instrument_name].append(abs_beat_time)

    def count_instruments_by_beat(self):
        inst_sum = 0
        binary_sum = 0
        max_instruments_at_once = 1
        min_instruments_at_once = len(self.instruments)
        means = []

        if len(self.instruments) < 2:
            print(f"LESS THAN 2 INSTRUMENTS: {self.mid.filename}")

        # gets the list of instruments that played at each beat
        for beat, inst_list in self.ordered_beats.items():
            # checks and sets the max and min instruments found
            inst_count = len(inst_list)
            if inst_count > max_instruments_at_once: max_instruments_at_once = inst_count
            if inst_count < min_instruments_at_once: min_instruments_at_once = inst_count

            if inst_count >= 2:
                binary_sum += 1

            inst_sum += inst_count

        # The Arithmetic Mean (sum of instruments from all beats divided by the amount of beats)
        arith_mean = float(inst_sum) / float(len(self.ordered_beats))
        return_data = ReturnData('am', len(self.instruments), arith_mean)
        means.append(return_data)

        # The Binary Mean (anything above 1 instrument counts as only 2 instruments)
        bin_mean = min_instruments_at_once + (float(binary_sum) / float(len(self.ordered_beats)))
        return_data = ReturnData('bm', len(self.instruments), bin_mean)
        means.append(return_data)

        return means

    def print_instrument_name(self, inst_id):
        inst_id = int(inst_id)
        if 33 < inst_id <= 81:
            print(PercussionDevicesEnum(inst_id))
        else:
            print(inst_id)

    def get_tubs_placement(self, attack_time):
        return int(math.ceil(float(attack_time) / (float(self.ticks_per_beat) / 12.0)))

    def create_timelines(self):
        # "instruments" is a dictionary where, for each element, the key is the instrument's name
        # and the value is a list of integers. In this list, each element represents the exact time,
        # in ticks, when an attack (note) happened. In order to transform it into the TUBS notation,
        # we must first fill the time differences between them with empty spaces (or dots, in the
        # text notation).
        print("\nINSTRUMENTOS:")
        for instrument_id, beats_ticks in self.instruments.items():            
            self.print_instrument_name(instrument_id)
            prev_tick = 0
            tubs = ""
            # The empty spaces should only be filled in the timeslots that aren't filled by beats
            # already. For instance, if there are beats on timeslots 4 and 7 of the TUBS system,
            # we should fill with [7 - (4+1)] = 2 beats, because the timeslots 4 and 7 are already
            # taken, leaving the timeslots 5 and 6 available to be filled.
            for tick in beats_ticks:
                tubs_tick = self.get_tubs_placement(tick)
                tubs_prev_tick = self.get_tubs_placement(prev_tick)

                for _ in range(tubs_prev_tick + 1, tubs_tick):
                    tubs += "."

                if tubs_prev_tick == tubs_tick and tick > 0:
                    pass
                else:
                    tubs += "X"

                if tick == 0:
                    prev_tick = tick + 1
                else:
                    prev_tick = tick

            # filling the last TUBS timeslots, in case the last beat hasn't
            # occurred in the song's last available timeslot
            if self.get_tubs_placement(prev_tick) < self.get_tubs_placement(self.max_track_len):
                for t in range(self.get_tubs_placement(prev_tick) + 1,
                               self.get_tubs_placement(self.max_track_len) + 1):
                    tubs += "."

            print(f"{tubs}\t{self.get_tubs_placement(prev_tick)}-"
                    f"{self.get_tubs_placement(self.max_track_len)}"),
            print(f"[Length: {len(tubs)}]")

    def format_results_for_file_writing(self):
        return self.filename + "\t\t" + str(self.max_track_len) + "\t\t" + \
               str(len(self.instruments)) + "\t\t" + str(self.numerator) + "/" + \
               str(self.denominator) + "\t\t" + str(self.ticks_per_beat) + "\n"


class ReturnData():
    def __init__(self, mean_type="", num_insts=0, mean_value=0.0):
        self.mean_type = mean_type
        self.num_insts = num_insts
        self.mean_value = mean_value


if __name__ == '__main__':
    from time import localtime, strftime
    import argparse

    parser = argparse.ArgumentParser(description='Running the processor module by itself.')
    parser.add_argument('-file', '-f', type=str, help='the file path')

    args = parser.parse_args()
    print(f"Begin: {strftime('%Y_%m_%d___%H_%M_%S', localtime())}")
    processor = MidiProcessor(args.file, args.file.split('/')[-1],
                              strftime("%Y_%m_%d___%H_%M_%S", localtime()))
    processor.process_tracks()
    if len(list(processor.beats)) > 0:
        processor.setup_variables()
        processor.beats_by_instrument()
        processor.create_timelines()
        processor.format_results_for_file_writing()
    else:
        print(f"Found no beats on file {args.file}.")
        
    print(f"End: {strftime('%Y_%m_%d___%H_%M_%S', localtime())}")