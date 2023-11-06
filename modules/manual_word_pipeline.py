'''
Module contains class ManualAttack for from-scratch approach on string-level (not df-level).
'''

#Imports
import random
import string
import re

import language_tool_python
from gensim.parsing.preprocesser import remove_stopwords
from gensim.utils import tokenize
from sentence_transformers import util

from modules.nrc_tool import nrc_affect_dict, nrc_affect_freqs, nrc_top_emotions

class ManualAttack:
    '''
    Class ManualAttack containing all functions needed for manual word-level substitution strategies.
    '''

    def __init__(self, text_, 
                 lexicon_=wordlex, 
                 embeddings_=glove_vectors, sentence_model_=sent_sim_model, 
                 lang_tool_=lang_tool, 
                 word_sim_=0.60, sent_sim_=0.60):
        '''
        Initialising function. Takes a number of default parameters. 
        Only the word and sentence similarity scores should be changed for testing purposes.
        Further parameter:
            text_: A lowercase text message to be adversarially attacked.
        Returns nothing
        '''
        self.text = text_.lower()
        self.lexicon = lexicon_
        self.embeddings = embeddings_
        self.sentence_model = sentence_model_
        self.lang_tool = lang_tool_
        self.word_sim = word_sim_
        self.sent_sim = sent_sim_
        self.affect_freqs = nrc_affect_freqs(self.text)
        self.top_emotions = nrc_top_emotions(self.text)

    def non_emotional_replacement(self, word):
        '''
        Function that looks for perturbation candidates if no emotional word was found in the text.
        Parameter:
            -word: A word isolated from the text message.
        Returns:
            -most_similar_dict: Dictionary with similarity scores containing similar words that do possess some emotion
        '''
        most_similar = self.embeddings.most_similar(word, topn=50) # Find most similar words, number 50 is arbitrarily chosen
        most_similar_dict = list({key: val for key, val in most_similar if key in self.lexicon.index}.keys()) # perturbation candidate must have some emotion
        return most_similar_dict
    
    def emotional_replacement(self, word):
        pass

    def lang_check(self, new_text):
        '''
        Functions performs language/grammar check on two strings.
        Will fix in second string only the fixes that are found on top of the ones found in first string.
        Parameters:
            -new_text: Second string with one word-level substitution compared to first
        Returns:
            -str2_fixed: Grammar-fixed second string, using only the fixes found on top of the first string's ones.
        '''

        # Find language errors in both string
        matches_1, matches_2 = self.lang_tool.check(self.text), self.lang_tool.check(new_text)

        # Look for that one fix
        found_fixes = []
        while not found_fixes:
            try:
                # Find the inserted error
                # Only if there is a higher amount of errors in the new string, a correction must take place.
                if len(matches_1) < len(matches_2):
                    for i, match in enumerate(matches_2):
                        if match.message != matches_1[i].message:
                            found_fixes.append(match)
                # In any other case or if found_fixes stays empty, the while-loop is aborted
                break
            # In case the previous loop leads to an indexerror, we have arrived at the final message
            except IndexError:
                found_fixes.append(matches_2[-1])

        new_text_fixed = language_tool_python.utils.correct(new_text, found_fixes)
        return new_text_fixed

    def sentence_similarity(self, sent_list):
        '''
        Function to evaluate sentence similarity between original text message and perturbed sentence.
        Parameters:
            -sent_list: Two-item list containing, firstly, the original text and secondly, the perturbed sentence
        Returns
            -sent_simil: Boolean, True if sentence similarity is above set threshold in __init__.
        '''
        sent_simil = False
        sent_embedding_1 = self.sentence_model.encode(sent_list[0], convert_to_tensor=True)
        sent_embedding_2 = self.sentence_model.encode(sent_list[1], convert_to_tensor=True)
        if util.pytorch_cos_sim(sent_embedding_1, sent_embedding_2).item() >= self.sent_sim:
            sent_simil = True
        return sent_simil
    
    def non_emotional_pipeline(self):
        '''
        Function that performs full word-substitution algorithm in case of emotionlessness in original text.
        Returns:
            -new_text: perturbed sentence that passes all checks
            OR a statement of unsuccessfulness
        '''

        #target words become cleaned tokens of sentence
        clean_sentence = remove_stopwords(self.text)
        target_words_prio = list(tokenize(clean_sentence.translate(str.maketrans("", "", string.punctuation))))
        random.shuffle(target_words_prio)

        for word in target_words_prio:
            if self.embeddings.__contains__(word): # target word must be in GloVe vocab
                for candidate in self.non_emotional_replacement(word):
                    new_text = self.lang_check(re.sub(word, candidate, self.text))

                    # The string must comply to three requirements
                    # 1) The sentence must be semantically similar enough
                    # 2) The language corrector may not grammar-correct the perturbed sentence back to itself, 
                    # 3) The language corrector may not grammar-correct the perturbed sentence to a version 
                    # that changes the sentiment of the perturbation candidate (conjugations that are not fully encapsulated in wordlex).
                    if new_text != self.text and self.sentence_similarity([self.text, new_text]) and nrc_affect_freqs(new_text) != self.affect_freqs: 
                        return new_text # return attack if found similar enough
        return "No adversarial attack found." # statement of unsuccessfulness

    def full_pipeline(self):

        #Take prioritised list of target words from nrc functions and apriori affect_freqs and top_emotions
        target_words_prio = list(nrc_affect_dict(self.text).keys())

        # If sentece is currently a-emotional, we will try to attack some emotion into them.
        # A randomly shuffled order of words in the sentence (tokenized and rid of punctuation) is set as words priority.
        if not target_words_prio:
            return self.non_emotional_pipeline()
