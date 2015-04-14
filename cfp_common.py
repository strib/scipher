class CfpCommon(object):
     maxv = 0
     commons = {}

     @staticmethod
     def register_common(common):
          v = common.version()
          if v > CfpCommon.maxv:
               CfpCommon.maxv = v
          CfpCommon.commons[common.version()] = common

     @staticmethod
     def get_latest_common():
          return CfpCommon.get_common_for_version(CfpCommon.maxv)

     @staticmethod
     def get_common_for_version(version):
          if version in CfpCommon.commons:
               return CfpCommon.commons[version]()
          return None

     @staticmethod
     def conf_names_filename():
          return "cfp_conf_names.txt"

     # This isn't likely to change in other grammar versions since we
     # need to do this before we can even figure out the version in
     # the first place
     @staticmethod
     def conf_name_from_index(f, index):
          last_4byte_line = 9576
          last_5byte_line = 114552
          # now find the right conf name by jumping to the right place
          # in the conf name file.  The first 9576 lines are 4 bytes
          # each, the next 104976 lines are 5 bytes each, and the
          # remaining lines are 6 bytes each
          line_at_byte = 4*(min(last_4byte_line, index))
          if index > last_4byte_line:
               line_at_byte += 5*(min(last_5byte_line-last_4byte_line,
                                      index-last_4byte_line))
          if index > last_5byte_line:
               line_at_byte += 6*(index-last_5byte_line)

          f.seek(line_at_byte, 0)
          return f.readline().rstrip()

     ## abstract interface below ##

     @staticmethod
     def version():
          raise NotImplementedError("")

     def chars_to_remove_a_space_before(self):
          raise NotImplementedError("")

     def chars_to_remove_a_space_after(self):
          raise NotImplementedError("")

     def list_recursive_terms(self):
          raise NotImplementedError("")

     def append_newlines(self):
          raise NotImplementedError("")

     def choose_last_or_notes(self):
          raise NotImplementedError("")

     def calc_list_bits(self, msg_len, body_prod):
          raise NotImplementedError("")

     def header_cfg_filename(self):
          raise NotImplementedError("")

     def body_cfg_filename(self):
          raise NotImplementedError("")

import versions.v000.cfp_common_v0
import cfp_common_v1
