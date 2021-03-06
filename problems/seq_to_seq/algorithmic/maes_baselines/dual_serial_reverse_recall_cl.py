#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright (C) IBM Corporation 2018
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""dual_serial_reverse_recall_cl.py: Contains definition of dual serial-reverse recall problem with control markers and command lines"""
__author__ = "Tomasz Kornuta"

import torch
import numpy as np
from problems.problem import DataTuple
from problems.seq_to_seq.algorithmic.algorithmic_seq_to_seq_problem import AlgorithmicSeqToSeqProblem, AlgSeqAuxTuple


class DualSerialReverseRecallCommandLines(AlgorithmicSeqToSeqProblem):
    """
    Class generating sequences of random bit-patterns and targets forcing the
    system to learn reverse recall problem.

    1. There are three markers, indicating:

    - beginning of storing/memorization,
    - beginning of forward recalling from memory and
    - beginning of reverse recalling from memory.


    2. Additionally, there is a command line (4th command bit) indicating whether given item is to be stored in memory (0) or recalled (1).

    """

    def __init__(self, params):
        """
        Constructor - stores parameters. Calls parent class initialization.

        :param params: Dictionary of parameters.
        """
        # Call parent constructor - sets e.g. the loss function, dtype.
        # Additionally it extracts "standard" list of parameters for
        # algorithmic tasks, like batch_size, numbers of bits, sequences etc.
        super(DualSerialReverseRecallCommandLines, self).__init__(params)

        assert self.control_bits >= 4, "Problem requires at least 4 control bits (currently %r)" % self.control_bits
        assert self.data_bits >= 1, "Problem requires at least 1 data bit (currently %r)" % self.data_bits

    def generate_batch(self):
        """
        Generates a batch  of size [BATCH_SIZE, 2*SEQ_LENGTH+2,
        CONTROL_BITS+DATA_BITS]. Additional elements of sequence are  start and
        stop control markers, stored in additional bits.

        : returns: Tuple consisting of: input [BATCH_SIZE, 2*SEQ_LENGTH+2, CONTROL_BITS+DATA_BITS],
        output [BATCH_SIZE, 2*SEQ_LENGTH+2, DATA_BITS],
        mask [BATCH_SIZE, 2*SEQ_LENGTH+2]

        TODO: every item in batch has now the same seq_length.

        """
        # Define control channel bits.
        # ctrl_main = [0, 0, 0, 0] # not really used.
        #ctrl_aux = [0, 0, 0, 1]

        ctrl_aux = np.zeros(self.control_bits)
        if (self.control_bits == 4):
            ctrl_aux[3] = 1  # [0, 0, 0, 1]
        else:
            if self.randomize_control_lines:
                # Randomly pick one of the bits to be set.
                ctrl_bit = np.random.randint(3, self.control_bits)
                ctrl_aux[ctrl_bit] = 1
            else:
                ctrl_aux[self.control_bits - 1] = 1

        # Markers.
        marker_start_main = np.zeros(self.control_bits)
        marker_start_main[0] = 1  # [1, 0, 0, 0]
        marker_start_aux_serial = np.zeros(self.control_bits)
        marker_start_aux_serial[1] = 1  # [0, 1, 0, 0]
        marker_start_aux_reverse = np.zeros(self.control_bits)
        marker_start_aux_reverse[2] = 1  # [0, 0, 1, 0]

        # Set sequence length.
        seq_length = np.random.randint(
            self.min_sequence_length, self.max_sequence_length + 1)

        # Generate batch of random bit sequences [BATCH_SIZE x SEQ_LENGTH X
        # DATA_BITS]
        bit_seq = np.random.binomial(
            1, self.bias, (self.batch_size, seq_length, self.data_bits))

        # 1. Generate inputs.
        # Generate input:  [BATCH_SIZE, 3*SEQ_LENGTH+3, CONTROL_BITS+DATA_BITS]
        inputs = np.zeros([self.batch_size,
                           3 * seq_length + 3,
                           self.control_bits + self.data_bits],
                          dtype=np.float32)
        # Set start main control marker.
        inputs[:, 0, 0:self.control_bits] = np.tile(
            marker_start_main, (self.batch_size, 1))

        # Set bit sequence.
        inputs[:, 1:seq_length + 1,
               self.control_bits:self.control_bits + self.data_bits] = bit_seq

        # Set start aux serial recall control marker.
        inputs[:, seq_length + 1, 0:self.control_bits] = np.tile(
            marker_start_aux_serial, (self.batch_size, 1))
        inputs[:,
               seq_length + 2:2 * seq_length + 2,
               0:self.control_bits] = np.tile(ctrl_aux,
                                              (self.batch_size,
                                               seq_length,
                                               1))

        # Set start aux serial reverse control marker.
        inputs[:, 2 * seq_length + 2, 0:self.control_bits] = np.tile(
            marker_start_aux_reverse, (self.batch_size, 1))
        inputs[:, 2 * seq_length + 3:3 * seq_length + 3,
               0:self.control_bits] = np.tile(ctrl_aux, (self.batch_size, seq_length, 1))

        # 2. Generate targets.
        # Generate target:  [BATCH_SIZE, 3*SEQ_LENGTH+3, DATA_BITS] (only data
        # bits!)
        targets = np.zeros([self.batch_size, 3 * seq_length + 3,
                            self.data_bits], dtype=np.float32)
        # Set bit sequence for serial recall.
        targets[:, seq_length + 2:2 * seq_length + 2, :] = bit_seq
        # Set bit sequence for reverse recall.
        targets[:, 2 * seq_length + 3:, :] = np.fliplr(bit_seq)

        # 3. Generate mask.
        # Generate target mask: [BATCH_SIZE, 3*SEQ_LENGTH+3]
        mask = torch.zeros([self.batch_size, 3 * seq_length + 3]
                           ).type(torch.ByteTensor)
        mask[:, seq_length + 2:2 * seq_length + 2] = 1
        mask[:, 2 * seq_length + 3:] = 1

        # PyTorch variables.
        ptinputs = torch.from_numpy(inputs).type(self.dtype)
        pttargets = torch.from_numpy(targets).type(self.dtype)

        # Return tuples.
        data_tuple = DataTuple(ptinputs, pttargets)
        aux_tuple = AlgSeqAuxTuple(mask, seq_length, 1)

        return data_tuple, aux_tuple

    # method for changing the maximum length, used mainly during curriculum
    # learning
    def set_max_length(self, max_length):
        self.max_sequence_length = max_length


if __name__ == "__main__":
    """ Tests sequence generator - generates and displays a random sample"""
    
    # "Loaded parameters".
    from utils.param_interface import ParamInterface 
    params = ParamInterface()
    params.add_custom_params({'control_bits': 4, 'data_bits': 8, 'batch_size': 2,
                              # 'randomize_control_lines': True,
                              'min_sequence_length': 1, 'max_sequence_length': 10})
    # Create problem object.
    problem = DualSerialReverseRecallCommandLines(params)
    # Get generator
    generator = problem.return_generator()
    # Get batch.
    data_tuple, aux_tuple = next(generator)
    # Display single sample (0) from batch.
    problem.show_sample(data_tuple, aux_tuple)
