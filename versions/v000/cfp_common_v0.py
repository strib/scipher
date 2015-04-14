# This file is for GRAMMAR_VERSION == 0.  Future versions may have to wrap it
# in a class to access it when decoding older grammars.

import cfp_common
import nltk
import sys

class CfpCommonV0(cfp_common.CfpCommon):
     # top-level section -> (list weight, list nonterminal for that section)
     list_weights = {nltk.Nonterminal("CFP_TOPIC_SECTION"):
                     (1,nltk.Nonterminal("CFP_TOPIC_LIST")),
                     nltk.Nonterminal("LOC_SECTION"):
                     (.5,nltk.Nonterminal("LOC_LIST")),
                     nltk.Nonterminal("ORGS_SECTION"):
                     (1,nltk.Nonterminal("ORGS_LIST")),
                     nltk.Nonterminal("STEER_SECTION"):
                     (1,nltk.Nonterminal("STEER_LIST")),
                     nltk.Nonterminal("KEYNOTE_SECTION"):
                     (7,nltk.Nonterminal("KEYNOTE_LIST")),
                     nltk.Nonterminal("PC_SECTION"):
                     (5,nltk.Nonterminal("PC_LIST"))}

     recursive_terms = [nltk.Nonterminal("CFP_TOPIC_LIST"),
                        nltk.Nonterminal("PROF_LIST_PAREN"),
                        nltk.Nonterminal("PROF_LIST_COMMA"),
                        nltk.Nonterminal("PROF_LIST_DASH"),
                        nltk.Nonterminal("LOC_LIST"),
                        nltk.Nonterminal("KEYNOTE_LIST_DASH")]

     newline_terms = {nltk.Nonterminal("CFP_GREETING"):1,
                      nltk.Nonterminal("CFP_TOPIC_HEADER"):1,
                      nltk.Nonterminal("CFP_TOPIC_LIST_ITEM"):1,
                      nltk.Nonterminal("PROF_LIST_PAREN_ITEM"):1,
                      nltk.Nonterminal("PROF_LIST_COMMA_ITEM"):1,
                      nltk.Nonterminal("PROF_LIST_DASH_ITEM"):1,
                      nltk.Nonterminal("KEYNOTE_ITEM_DASH"):1,
                      nltk.Nonterminal("ORGS_HEADER"):1,
                      nltk.Nonterminal("PC_HEADER"):1,
                      nltk.Nonterminal("STEER_HEADER"):1,
                      nltk.Nonterminal("KEYNOTE_HEADER"):1,
                      nltk.Nonterminal("LOC_HEADER"):1,
                      nltk.Nonterminal("LOC_PLACE_ITEM"):1,
                      nltk.Nonterminal("LOC_UNIV_ITEM"):1,
                      nltk.Nonterminal("DATE_HEADER"):1,
                      nltk.Nonterminal("SUBSTITUTE_DATE_NL"):1,
                      nltk.Nonterminal("DATE_TYPE_1_NL"):1,
                      nltk.Nonterminal("DATE_TYPE_2_NL"):1,
                      nltk.Nonterminal("DATE_TYPE_3_NL"):1,
                      nltk.Nonterminal("DATE_TYPE_4_NL"):1,
                      nltk.Nonterminal("CFP_INTRO_SECTION"):1,
                      nltk.Nonterminal("CFP_SCOPE_SECTION"):1,
                      nltk.Nonterminal("CFP_SUBMIT_SECTION"):1,
                      nltk.Nonterminal("SPACE_NEWLINE"):1}

     last_or_not_terms = {nltk.Nonterminal("SUBMIT_CLOSING"):False}

     @staticmethod
     def version():
          return 0

     def chars_to_remove_a_space_before(self):
          return '.,:;\?\)\!'

     def chars_to_remove_a_space_after(self):
          return '\('

     def list_recursive_terms(self):
          return CfpCommonV0.recursive_terms

     def append_newlines(self):
          return CfpCommonV0.newline_terms

     def choose_last_or_nots(self):
          return CfpCommonV0.last_or_not_terms

     def calc_list_bits(self, msg_len, body_prod):
          # we only care about lists that are actually used in the body
          used_lists = {w[1]: w[0] for l,w in self.list_weights.iteritems()
                        if l in body_prod.rhs()}

          total_weight = sum(used_lists.values())
          # we'll get most of our entropy from lists, but we should make
          # sure that the bits are spread out among the lists as much as
          # possible.  So given a set of lists, each with weight w (total
          # weight of W), and a number of bits remaining = B, make sure
          # B*w/W bits are used up in this list.  Multiply by some fraction
          # since other parts of the message will use some bits too.
          fraction_in_lists = 0.85

          list_bits = {}
          for l,w in used_lists.iteritems():
               list_bits[l] = int(msg_len*fraction_in_lists*w/total_weight)
          return list_bits

     def header_cfg_filename(self):
          return "versions/v000/cfp_header.cfg"

     def body_cfg_filename(self):
          return "versions/v000/cfp_body.cfg"

cfp_common.CfpCommon.register_common(CfpCommonV0)
