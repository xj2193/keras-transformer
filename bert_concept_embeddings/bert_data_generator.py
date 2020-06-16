# +
import random
from itertools import islice, chain
from typing import List, Callable, Optional, Sequence

import numpy as np
# noinspection PyPep8Naming
from keras import backend as K
from keras.utils import get_custom_objects
# -

from keras.preprocessing.text import Tokenizer

BERT_SPECIAL_TOKENS = ['[MASK]', '[UNUSED]']


class ConceptTokenizer:
    
    def __init__(self, special_tokens: Optional[Sequence[str]] = None, oov_token='0'):
        self.special_tokens = special_tokens
        self.tokenzier = Tokenizer(oov_token=oov_token, filters='', lower=False)
        
    def fit_on_concept_sequences(self, concept_sequences):
        self.tokenzier.fit_on_texts(concept_sequences)
        if self.special_tokens is not None:
            self.tokenzier.fit_on_texts(self.special_tokens)
        
    def encode(self, concept_sequences):
        return self.tokenzier.texts_to_sequences(concept_sequences)
    
    def decode(self, concept_sequence_token_ids):
        return self.tokenzier.sequences_to_texts(concept_sequence_token_ids)
    
    def get_first_token_index(self):
        return min(list(self.tokenzier.index_word.keys()))
    
    def get_last_token_index(self):
        return max(list(self.tokenzier.index_word.keys()))
    
    def get_vocab_size(self):
        return len(self.tokenzier.index_word)


class BatchGeneratorVisitBased:
    """
    This class generates batches for a BERT-based language model
    in an abstract way, by using an external function sampling
    sequences of token IDs of a given length.
    """

    def __init__(self, concept_sequences,
                 mask_token_id: int,
                 unused_token_id: int,
                 max_sequence_length: int,
                 batch_size: int, 
                 first_normal_token_id:int, 
                 last_normal_token_id:int):
        
        self.concept_sequences = concept_sequences
        self.data_size = len(concept_sequences)
        self.steps_per_epoch = (
            # We sample the dataset randomly. So we can make only a crude
            # estimation of how many steps it should take to cover most of it.
            self.data_size // batch_size)
        self.batch_size = batch_size
        self.max_sequence_length = max_sequence_length
        self.mask_token_id = mask_token_id
        self.unused_token_id = unused_token_id
        self.first_token_id = first_normal_token_id
        self.last_token_id = last_normal_token_id
        self.index = 0

    def generate_batches(self):
        """
        Keras-compatible generator of batches for BERT (can be used with
        `keras.models.Model.fit_generator`).

        Generates tuples of (inputs, targets).
        `inputs` is a list of two values:
            1. masked_sequence: an integer tensor shaped as
               (batch_size, sequence_length), containing token ids of
               the input sequence, with some words masked by the [MASK] token.
            2. segment id: an integer tensor shaped as
               (batch_size, sequence_length),
               and containing 0 or 1 depending on which segment (A or B)
               each position is related to.

        `targets` is also a list of two values:
            1. combined_label: an integer tensor of a shape
               (batch_size, sequence_length, 2), containing both
               - the original token ids
               - and the mask (0s and 1s, indicating places where
                 a word has been replaced).
               both stacked along the last dimension.
               So combined_label[:, :, 0] would slice only the token ids,
               and combined_label[:, :, 1] would slice only the mask.
            2. has_next: a float32 tensor (batch_size, 1) containing
               1s for all samples where "sentence B" is directly following
               the "sentence A", and 0s otherwise.
        """
        while True:
            
            if self.index >= self.data_size:
                self.index = 0
            
            concept_sequence_batch = islice(self.concept_sequences, self.index, self.index + self.batch_size)
            self.index += self.batch_size
            
            next_bunch_of_samples = self.generate_samples(concept_sequence_batch)
            
            mask, sequence, masked_sequence = zip(*list(next_bunch_of_samples))
            
            combined_label = np.stack([sequence, mask], axis=-1)
            
            yield (
                [np.array(masked_sequence)],
                [combined_label]
            )

    def generate_samples(self, concept_sequence_batch):
        """
        Generates samples, one by one, for later concatenation into batches
        by `generate_batches()`.
        """
        results = []
        
        for sequence in concept_sequence_batch:   
            masked_sequence = sequence.copy()
            output_mask = np.zeros((len(sequence),), dtype=int)

            for word_pos in range(0, len(sequence)):
                
                if sequence[word_pos] == self.unused_token_id:
                    break
                if random.random() < 0.15:
                    dice = random.random()
                    if dice < 0.8:
                        masked_sequence[word_pos] = self.mask_token_id
                    elif dice < 0.9:
                        masked_sequence[word_pos] = random.randint(
                            self.first_token_id, self.last_token_id)
                    # else: 10% of the time we just leave the word as is
                    output_mask[word_pos] = 1
            results.append((output_mask, sequence, masked_sequence))
        
        return results

