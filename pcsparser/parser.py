#!/usr/bin/env python3

import re
import sys
import os
import numpy as np
from enum import Enum
from abc import ABC

class PCSObject(ABC):
    """
        General data structure to keep the pcs file in.

        Fields are added by functions, such that checks can be conducted.
    """
    def __init__(self):
        self.params = []

    def add_param(self, name: str, structure: str = "int", domain: list = [-sys.maxsize, sys.maxsize], scale: str = "linear", default: str = "0", comment: str = None):
        assert structure in ["integer", "real", "categorical", "ordinal"]

        #Domain check
        if structure in ["int", "real"]:
            assert len(domain) == 2
            pass
        elif structure == "categorical":
            #TODO check categories
            scale = None


        param = {
            "name": name,
            "structure": structure,
            "domain": domain,
            "scale": scale,
            "default": default,
            "comment": comment,
            "type": "parameter",
        }

        self.params.append(param)

    def add_constraint(self, **kwargs):
        # TODO add checks
        self.params.append({**kwargs, "type": "constraint"})

    def add_forbidden(self, **kwargs):
        # TODO add checks
        self.params.append({**kwargs, "type": "forbidden"})

    def add_comment(self, **kwargs):
        # TODO add checks
        self.params.append({**kwargs, "type": "comment"})

    def clear(self):
        self.params = []


class PCSConvention(Enum):
    """
    Internal pcs convention enum
    """
    unknown = ""
    SMAC = "smac"
    ParamILS = "paramils"


class PCSParser(ABC):
    """
        Base interface object for the parser.

        It loads the pcs files into the generic pcs object. Once a parameter file is loaded, it can be exported to another
        file
    """

    def __init__(self,inherit=None):
        if inherit is None:
            self.pcs = PCSObject()
        else:
            self.pcs = inherit.pcs

    @staticmethod
    def _format_string_to_enum(string: str) -> PCSConvention:
        for form in PCSConvention:
            if form.value == string:
                return form

        raise Exception("ERROR: parameter configuration space format is not supported.")
        sys.exit()


    def check_validity(self) -> bool:
        """
        Check the validity of the pcs
        """

        #TODO implement

        #check if for all parameters in constraints and forbidden clauses exists
        #Check for conflict between default values and constraints and forbidden clauses
        return True

    def load(self, filepath: str, convention: str = "smac"):
        """
        Main import function
        """
        convention = self._format_string_to_enum(convention)

        #TODO check if file actually exists
        lines = []
        with open(filepath, "r") as fh:
            lines = fh.readlines()
            fh.close()

        if convention == PCSConvention.SMAC:
            parser = SMACParser(self)
            parser.parse(lines)
            self.pcs = parser.pcs
        else:
            raise Exception("ERROR: Importing the pcs convention for {} is not yet implemented.".format(convention.value))

    def export(self, convention: str = "smac", destination: str = None):
        """
        Main export function
        """
        convention = self._format_string_to_enum(convention)
        if convention == PCSConvention.ParamILS:
            pcs = ParamILSParser(self).compile()
        else:
            raise Exception("ERROR: Exporting the pcs convention for {} is not yet implemented.".format(convention.value))

        with open(destination, "w") as fh:
            fh.write(pcs)
            fh.close()


class SMACParser(PCSParser):
    def parse(self, lines: list[str]):
        self.pcs.clear()

        # PARAMS
        for line in lines:
            # the only forbidden characters in parameter names are spaces, commas, quotes, and parentheses
            regex = r"(?P<name>[^\s\"',]*)\s+(?P<structure>\w*)\s+(?P<domain>(\[|\{).*(\]|\}))\s*\[(?P<default>.*)\]\s*(?P<scale>log)*\s*#*(?P<comment>.*)"
            m = re.match(regex, line)
            if m is not None:
                fields = m.groupdict()
                fields["domain"] = re.sub(r"(?:\[|\]|\{|\})", "", fields["domain"])
                fields["domain"] = re.split(r"\s*,\s*", fields["domain"])
                self.pcs.add_param(**fields)
                continue

            # CONSTRAINTS
            regex = r"(?P<parameter>\w+)\s*\|(?P<conditions>.+)\s*#*(?P<comment>.*)"
            m = re.match(regex, line)
            if m is not None:
                constraint = m.groupdict()
                constraint["conditions"] = self._parse_conditions(constraint["conditions"])

                self.pcs.add_constraint(**constraint)
                continue

            # FORBIDDEN CLAUSES
            regex = r"\s*\{(?P<clauses>[^\}]+)\}\s*#*(?P<comment>.*)"
            m = re.match(regex, line)
            if m is not None:
                forbidden = m.groupdict()
                conditions = []

                # Simple clauses
                # {<parameter name 1>=<value 1>, ..., <parameter name N>=<value N>}
                if "," in forbidden["clauses"]:
                    forbidden["clause_type"] = "simple"

                    for clause in re.split(r"\s*,\s*", forbidden["clauses"]):
                        m = re.match(r"(?P<param>[^\s\"',=]+)\s*=\s*(?P<value>[^\s\"',]+)", clause)
                        if m is not None:
                            conditions.append(m.groupdict())
                        else:
                            print(clause, "ERROR")

                else:  # Advanced clauses
                    forbidden["clause_type"] = "advanced"
                    # TODO decide if we need to further parse this down
                    conditions = [expr for expr in re.split(r"\s*(?:\|\||&&)\s*", forbidden["clauses"])]

                if len(conditions) == 0:
                    raise Exception(f"ERROR: cannot parse the following line: \n'{line}'")

                forbidden["clauses"] = conditions

                self.pcs.add_forbidden(**forbidden)
                continue

            # COMMENTLINE
            regex = r"\s*#(?P<comment>.*)"
            m = re.match(regex, line)
            if m is not None:
                comment = m.groupdict()
                self.pcs.add_comment(**comment)
                continue

            # EMTPY LINE
            regex = r"^\s*$"
            m = re.match(regex, line)
            if m is not None:
                continue

            # RAISE ERROR
            raise Exception(f"ERROR: cannot parse the following line: \n'{line}'")

        return

    def _parse_conditions(self, conditions: str) -> list[tuple]:
        conditionlist = []
        condition = None
        operator = None
        nested = 0
        nested_start = 0
        condition_start = 0
        for pos, char in enumerate(conditions):
            # Nested clauses
            if char == "(":
                if nested == 0:
                    nested_start = pos
                nested += 1
            elif char == ")":
                nested -= 1
                if nested == 0:
                    condition = self._parse_conditions(conditions[nested_start + 1:pos])
                    conditionlist.append((operator, condition))
                    if (pos+1) == len(conditions):
                        return conditionlist

            if pos > 1 and nested == 0:
                for op in ["||", "&&"]:
                    if conditions[pos - 1: pos + 1] == op:
                        if not isinstance(condition, list):
                            condition = self._parse_condition(conditions[condition_start:pos - 1])
                            conditionlist.append((operator, condition))

                        operator = op
                        condition_start = pos + 1

        condition = self._parse_condition(conditions[condition_start:len(conditions)])
        conditionlist.append((operator, condition))

        return conditionlist

    @staticmethod
    def _parse_condition(condition: str) -> dict:
        cont = True

        m = re.match(
            r"\s*(?P<parameter>[^\s\"',]+)\s*(?P<quantifier>==|!=|<|>|<=|>=)\s*(?P<value>[^\s\"',]+)\s*",
            condition)
        if m is not None:
            condition = {
                **m.groupdict(),
                "type": "numerical",
            }
            cont = False

        if cont:
            m = re.match(r"\s*(?P<parameter>[^\s\"',]+)\s+in\s*\{(?P<items>[^\}]+)\}\s*", condition)
            if m is not None:
                condition = {
                    **m.groupdict(),
                    "type": "categorical",
                }
                condition["items"] = re.split(r",\s*", condition["items"])

        if not cont:
            raise Exception(f"ERROR: Couldn't parse '{condition}'")

        return condition

    def compile(self) -> str:
        #TODO implement
        pass


class ParamILSParser(PCSParser):
    def parse(self, lines: list[str]):
        # TODO implement
        pass

    def compile(self) -> str:
        # TODO Produce warning if certain specifications cannot be kept in this format

        # TODO introduce granularity parameter that sets how log and real ranges should be expanded
        granularity = 20

        lines = []
        for item in self.pcs.params:
            if item["type"] == "parameter":
                if item["structure"] in ["ordinal", "categorical"]:
                    domain = ",".join(item["domain"])
                elif item["structure"] == "integer":
                    assert len(item["domain"]) == 2

                    (minval, maxval) = [int(i) for i in item["domain"]]
                    if item["scale"] != "log":
                        domain = f"{minval}, {(minval + 1)}..{maxval}"
                    else:
                        domain = list(np.unique(np.geomspace(minval, maxval, granularity, dtype=int)))
                        # add default value
                        if int(item["default"]) not in domain:
                            domain += [int(item["default"])]
                            domain.sort()

                        domain = ",".join([str(i) for i in domain])

                elif item["structure"] == "real":
                    assert len(item["domain"]) == 2

                    (minval, maxval) = [float(i) for i in item["domain"]]
                    if item["scale"] != "log":
                        stepsize = (maxval - minval) / granularity
                        default = float(item["default"])
                        domain = f"{minval}, {(minval + stepsize)}..{maxval}"
                        # TODO how to integrate the default
                    else:
                        domain = list(np.unique(np.geomspace(minval, maxval, granularity, dtype=float)))
                        # add default value
                        if float(item["default"]) not in domain:
                            domain += [float(item["default"])]
                            domain.sort()

                        domain = ",".join([f"{i}" for i in domain])

                domain = "{" + domain + "}"
                line = "{name} {domainl} [{default}]".format(**item, domainl=domain)
                if item["comment"] != "":
                    line += " #{}".format(item["comment"])

                lines.append(line)

        for item in self.pcs.params:
            if item["type"] == "constraint":
                line = "{parameter}|".format(**item)
                line += self._compile_conditions(item["conditions"])
                if item["comment"] != "":
                    line += " #{}".format(item["comment"])
                lines.append(line)

        for item in self.pcs.params:
            if item["type"] == "forbidden":
                if item["clause_type"] == "simple":
                    clauses = ["{param}={value}".format(**cls) for cls in item["clauses"]]
                    line = "{" + ",".join(clauses) + "}"
                    if item["comment"] != "":
                        line += "#{}".format(item["comment"])
                    lines.append(line)
                else:
                    print("WARNING: Advanced forbidden clauses are not supported by ParamILS.")
                pass

        lines = "\n".join(lines)
        return lines

    def _compile_conditions(self, conditions: list[tuple]) -> str:
        line = ""
        for operator, condition in conditions:
            if operator is not None:
                line += f" {operator} "

            if isinstance(condition, list):
                line += "({})".format(self._compile_conditions(condition))
                pass
            else:
                if condition["type"] == "numerical":
                    line += "{parameter} {quantifier} {value}".format(**condition)
                if condition["type"] == "categorical":
                    itemss = ", ".join(condition["items"])
                    line += "{parameter} in {{{itemss}}}".format(**condition, itemss=itemss)
        return line