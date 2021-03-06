from sqlparse_mod import parse, tokens


class SQLParser(object):
    """class used to parse sql statements into a data structure
    which can be used to execute the statement"""

    def parse_statement(self, statement):
        """converts a statement in string form to tokens and passes off to
        the parser"""

        def parse_tkns(tkns):
            """parse tokens into datastructure used to execute statement"""
            fns = {}
            joins = []
            aliases = {}
            cases = {}
            ops = {}
            self.case_num = 0
            nested_queries = {}

            # some helpers for determining a token's attributes when it isn't
            # completely straight forward
            is_identifier = lambda token: token._get_repr_name() == 'Identifier'
            is_case = lambda token: token._get_repr_name() == 'Case'
            is_function = lambda token: token._get_repr_name() == 'Function'
            is_comparison = lambda token: token._get_repr_name() == 'Comparison'

            def strip_tkns(tkns, punctuation=None):
                """convenience function to remove whitespace tokens and comments
                from list, optionally also remove punctuation"""
                if punctuation is None:
                    return [token for token in tkns if not token.is_whitespace()
                            and token._get_repr_name() != 'Comment']
                return [token for token in tkns if not token.is_whitespace()
                        and token._get_repr_name() != 'Comment'
                        and token.ttype != tokens.Token.Punctuation]

            def get_fns(tkns):
                """get a dictionary of all functions in statement, needed for
                order of operations with grouping and case statements"""
                for tkn in tkns:
                    if tkn._get_repr_name() == 'Function':
                        col, fn = sql_function(tkn)
                        _fns = fns.get(col, [])
                        if fn not in _fns:
                            _fns.append(fn)
                        fns[col] = _fns
                    elif tkn.is_group():
                        get_fns(tkn.tokens)

            def col_identifier(token):
                tkns = token.tokens
                # strip whitespace and punctuation
                tkns = strip_tkns(tkns)
                if len(tkns) == 1:
                    identifier = tkns[0].value
                    # handle issue of ambigous column names through aliasing
                    # for now, may be able to find a more efficient way in future
                    aliases[identifier] = None, None
                    return identifier, None

                # find the index of 'AS' in tkns
                as_idx = next((i for i, t in enumerate(tkns)
                               if t.value.upper() == 'AS'), None)
                if as_idx is None:
                    return tkns[0].value + '.' + tkns[-1].value, None

                as_name = tkns[as_idx+1].value
                tkns = tkns[:as_idx]
                if len(tkns) == 1:
                    # handle aliasing
                    if is_case(tkns[0]):
                        return parse_case(tkns[0].tokens, as_name=as_name)
                    elif is_identifier(tkns[0]):
                        aliases[as_name] = col_identifier(tkns[0]), None
                    elif is_function(tkns[0]):
                        col, fn = sql_function(tkns[0])
                        aliases[as_name] = col, fn
                    return as_name, None

                op_idx = next((i for i, t in enumerate(tkns)
                               if t.ttype == tokens.Operator), None)
                if op_idx is None:
                    # handle aliasing for special case where parser doesn't group
                    # identifier properly
                    aliases[as_name] = tkns[0].value + "." + tkns[-1].value, None
                    return as_name, None
                return operation(tkns, as_name)

            def sql_function(token):
                tkns = token.tokens
                fn, parens = tkns
                col = parens.tokens[1]
                fn = fn.value.lower()
                col = col_identifier(col)[0]
                return col, fn

            def identifier_list(token):
                """used to parse sql identifiers into actual
                table/column groupings"""
                if is_identifier(token):
                    return col_identifier(token)

                if is_function(token):
                    return [sql_function(token)]

                if is_case(token):
                    return parse_case(token)

                tkns = token.tokens
                if len(tkns) == 1:
                    if is_function(tkns[0]):
                        return sql_function(tkns[0])
                    return col_identifier(token)
                proc = []
                # filter whitespace and punctuation
                for tkn in tkns:
                    if is_identifier(tkn):
                        proc.append(col_identifier(tkn))
                    elif is_case(tkn):
                        proc.append(parse_case(tkn.tokens))
                    elif is_function(tkn):
                        col, fn = sql_function(tkn)
                        proc.append((col, fn))
                    elif not tkn.is_whitespace() \
                            and tkn.ttype != tokens.Punctuation:
                        proc.append(col_identifier(tkn))

                return proc

            def operation(tkns, as_name=None):
                """perform arithmetic operations"""
                # identifiers used in comparision, needed to work around issue
                # #83
                raise NotImplementedError("Aritmetic Operations not yet supported")
                # identifiers = {}

                # def get_str(token):
                #     # import pdb; pdb.set_trace()
                #     if is_function(token):
                #         col, fn = sql_function(col)
                #         col_str = (col+'_'+fn).replace('.', '_')
                #         identifiers[col_str] = col, fn
                #     elif token.is_group():
                #         col = col_identifier(col)[0]
                #         col_str = col.replace('.', '_')
                #         identifiers[col_str] = col, None
                #     else:
                #         return token.value
                #     return col_str

                # expr = "".join(map(get_str, tkns))
                # import pdb; pdb.set_trace()

                # # give auto-genereted name if no alias specified
                # if as_name is None:
                #     as_name = 'case' + str(self.case_num)
                # op = {'as_name': as_name,
                #       'expr': (expr, identifiers)}

                # _ops = ops.get(curr_sect, [])
                # _ops.append(op)
                # ops[curr_sect] = _ops
                # return as_name, None

            def comparison(comps, operators=None):
                # identifiers used in comparision, needed to work around issue #83
                identifiers = {}

                # need a counter for number of comparisons for variable names
                def comp_str(comp):
                    comp_map = {
                        '=': '==',
                        '<>': '!=',
                    }
                    comp = strip_tkns(comp)
                    assert len(comp) == 3
                    col, comp, val = comp
                    comp = comp_map.get(comp.value, comp.value)
                    if is_function(col):
                        col, fn = sql_function(col)
                        col_str = (col+'_'+fn).replace('.', '_')
                        identifiers[col_str] = col, fn
                    elif col.is_group():
                        col = col_identifier(col)[0]
                        col_str = col.replace('.', '_')
                        identifiers[col_str] = col, None
                    if val.is_group():
                        val = col_identifier(val)[0]
                        identifiers[val.replace('.', '_')] = val, None
                    else:
                        val = val.value
                    val_str = val.replace('.', '_')
                    return """({col} {comp} {val})""".format(col=col_str,
                                                             comp=comp,
                                                             val=val_str)

                comp = comps[0]
                ev_str = comp_str(comp)
                if operators is not None:
                    for comp, op in zip(comps[1:], operators):
                        # build string to eventually evaluate
                        if op == 'AND':
                            ev_str += " & " + comp_str(comp)
                        elif op == 'OR':
                            ev_str += " | " + comp_str(comp)

                return ev_str, identifiers

            def parse_case(tkns, as_name=None):
                def get_stmt(token):
                    if is_function(token):
                        return sql_function(token)
                    else:
                        return col_identifier(token)

                # give auto-genereted name if no alias specified
                if as_name is None:
                    self.case_num += 1
                    as_name = 'case' + str(self.case_num)
                case = {'as_name': as_name,
                        'stmts': []}
                # remove whitespace from tokens
                tkns = strip_tkns(tkns)
                # need to parse backwards for proper order of operations
                for i, token in reversed(list(enumerate(tkns))):
                    # stop at CASE as we are looping in reverse so will
                    # be starting at END
                    if token.ttype == tokens.Keyword.CASE:
                        break
                    elif tkns[i-1].value == 'ELSE':
                        case['else_stmt'] = get_stmt(token)
                    elif tkns[i-1].value == 'THEN':
                        stmt = get_stmt(token)
                    elif is_comparison(token):
                        if token.is_group():
                            cond = comparison([token.tokens])
                        else:
                            cond = comparison([[tkns[i-1], token,
                                                tkns[i+1]]])
                        case['stmts'].append((cond, stmt))

                _cases = cases.get(curr_sect, [])
                _cases.append(case)
                cases[curr_sect] = _cases
                return as_name, None

            def parse_select(tkns):
                identifiers = []
                tkns = strip_tkns(tkns)
                for i, token in enumerate(tkns):
                    if token.ttype is tokens.Wildcard:
                        return
                    elif is_identifier(token):
                        identifiers = [col_identifier(token)]
                    elif token.is_group():
                        identifiers = identifier_list(token)
                return identifiers

            def tbl_identifier(tkns):
                """returns identifier as tuple of
                tablename, identifier"""
                if len(tkns) == 1:
                    return (tkns[0].value,) * 2
                return tkns[0].value, tkns[-1].value

            def parse_from(tkns):
                how = None
                for i, token in enumerate(tkns):
                    if token._get_repr_name() == 'Parenthesis':
                        table, identifier = tbl_identifier(tkns[i+1].tokens)
                        table = '###temp_' + table
                        nested = parse_tkns(token.tokens[1:-1])
                        nested_queries[table] = nested
                        # remove next token from list as it is already processed
                        del tkns[i+1]
                    elif token.is_group():
                        table, identifier = tbl_identifier(token.tokens)
                    elif 'JOIN' in token.value:
                        how = token.value.split()[0].lower()
                        break
                if how is not None:
                    parse_join(tkns[i+1:], how)

                return table, identifier

            def parse_join(tkns, how):
                for i, token in enumerate(tkns):
                    if 'JOIN' in token.value:
                        how_new = token.value.split()[0].lower()
                        parse_join(tkns[i+1:], how_new)
                        break
                    elif token._get_repr_name() == 'Parenthesis':
                        right, right_identifier = tbl_identifier(tkns[i+1].tokens)
                        right = '###temp_' + right
                        nested = parse_tkns(token.tokens[1:-1])
                        nested_queries[right] = nested
                        # remove next token from list as it is already processed
                        del tkns[i+1]
                    elif is_comparison(token):
                        left_on = col_identifier(token.tokens[0])[0]
                        right_on = col_identifier(token.tokens[-1])[0]
                    elif token.is_group():
                        right, right_identifier = tbl_identifier(token.tokens)
                joins.append((right, how, left_on, right_on, right_identifier))

            def parse_where(tkns):
                # list of boolean indices to apply to current value
                comps = [token.tokens for token in tkns if is_comparison(token)]
                operators = [token.value for token in tkns
                             if token.value in ('AND', 'OR')]
                return comparison(comps, operators)

            def parse_group(tkns):
                for tkn in tkns:
                    if tkn.is_group():
                        group_by = zip(*identifier_list(tkn))[0]
                return group_by

            def parse_order(tkns):
                for token in tkns:
                    if token.is_group():
                        identifiers = identifier_list(token)
                return identifiers

            sections = {tokens.Keyword.SELECT: parse_select,
                        tokens.Keyword.FROM: parse_from,
                        tokens.Keyword.WHERE: parse_where,
                        tokens.Keyword.GROUP: parse_group,
                        tokens.Keyword.ORDER: parse_order}

            # remove whitespace from tokens
            tkns = strip_tkns(tkns)

            _parsed = {}
            for i, token in enumerate(tkns):
                if i == 0:
                    start = 0
                    curr_sect = token.value
                    continue
                if token.ttype in sections.keys():
                    _parsed[curr_sect] = \
                        sections[tkns[start].ttype](tkns[start:i])
                    # start next category of statement
                    start = i
                    curr_sect = token.value.upper()

            # add in last section
            _parsed[curr_sect] = sections[tkns[start].ttype](tkns[start:])

            get_fns(tkns)
            _parsed['FUNCTIONS'] = fns
            _parsed['JOINS'] = joins
            _parsed['ALIASES'] = aliases
            _parsed['CASES'] = cases
            _parsed['NESTED_QUERIES'] = nested_queries
            return _parsed

        tkns = parse(statement)[0].tokens
        return parse_tkns(tkns)
