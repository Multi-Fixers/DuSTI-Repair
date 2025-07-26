from setPath import understand



REL_KIND = [
    'Java Definein',        # The entity is defined in the current line.
    'Java Setby',           # The variable or field is set or modified.
    'Java Useby',           # The variable or field is used (read operation).
    'Java Callby',          # The method is called on the current line.
    'Java Modifyby',        # Indicates modifications to variables or fields.
    'Java Returnfrom',      # Return statements associated with methods.
]

CONTEXT_WINDOW_LENGTH = 1000

FILE = None
class BackwardSlicing(object):
    def __init__(self, db, file, buggy_line_num):
        self.db = db
        self.file = file
        self.buggy_line_num = buggy_line_num
        self.method_lines = []
        self.loops = {}
        self.conds = {}
        self.conditional_scope = {}
        self.statement_closure = {}
        self.scope = {}
        self.method_start_line_num = -1 # redundant
        self.function_variables = []
        self.has_function_call = False
        self.else_lines = set()
        # self.is_skip = True
        self.comment_lines = set()

        for lexeme in file.lexer():
            # get all the lines of the function/Class that buggy line in
            if lexeme.token() == "Comment":
                self.comment_lines.add(lexeme.line_begin())
            if lexeme.line_begin() == buggy_line_num:
                # print("lex",lexeme.text())
                contains = False
                if lexeme.ent():
                    # print(lexeme.text(),lexeme.ent().parent().kindname())
                    for word in ['Method', 'Class']:
                        if lexeme.ent().parent():
                            index = lexeme.ent().parent().kindname().find(word)
                            if index != -1:  
                                contains = True
                    # print(contains, lexeme.ent())

                # if lexeme.token() == 'Identifier' and lexeme.ent() and lexeme.ent().parent():
                #     # print(lexeme.ent().parent().kindname())
                #     lines = set()
                #     for ref in lexeme.ent().parent().refs():
                #         if not self.method_start_line_num:
                #             self.method_start_line_num = ref.line()
                #         if ref.kind().longname() not in ['Java Callby Nondynamic', 'Java Useby', 'Java Useby Deref Partial']:
                #             lines.add(ref.line())
                            # print(lexeme.ent().parent(),ref.line(),ref.kindname(),ref.kind().longname())
                if lexeme.token() == 'Identifier' and lexeme.ent() and lexeme.ent().parent() and contains and lexeme.ent().library() != "Standard":
                    lexeme.ent().library()
                    lines = set()
                    for ref in lexeme.ent().parent().refs():
                        if not self.method_start_line_num:
                            self.method_start_line_num = ref.line()
                        if ref.kind().longname() not in ['Java Callby Nondynamic', 'Java Useby', 'Java Useby Deref Partial']:
                            lines.add(ref.line())
                            # print(lexeme.ent().parent(),ref.line(),ref.kindname(),ref.kind().longname())
                    # print("lines",lines)
                    self.method_lines = sorted(lines)
        # print("lines",self.method_lines)
        # print("comments",self.comment_lines)

    def record_scope(self):
        """
        Records the scope (start and end lines) of blocks and variables and update self.scope .
        """
        brace_map = {'{': '}', '[': ']', '(': ')'}
        stack = []  # To track opening braces
        line_stack = []  # To track corresponding line keys
        is_variable = {}  # Tracks if a line corresponds to a variable declaration

        for lexeme in self.file.lexer():
            line_begin = lexeme.line_begin()
            line_key = str(line_begin)

            # Handle method declarations
            if "Method" in (lexeme.ent().kindname() if lexeme.ent() else ""):
                if lexeme.ent().library() != "Standard":
                    self.function_variables.append(line_begin)
                    
            # check-this
            if lexeme.ent() and "Variable" in lexeme.ent().kindname() and lexeme.ent().type() in ['{}', '[{}]', '[]']:
                is_variable[line_key] = True
            
            if lexeme.text() in ['{', '(', '[']:
                stack.append(lexeme.text())
                line_stack.append(line_key)
                self.scope[line_key] = {
                    'is_variable': is_variable.get(line_key, False),
                    'line_num_begin': line_begin,
                    'column_num_begin': lexeme.column_begin(),
                }

            # Handle closing braces
            elif lexeme.text() in ['}', ']', ')']:
                if stack and brace_map[stack[-1]] == lexeme.text():
                    # Pop the matching opening brace
                    stack.pop()
                    start_line_key = line_stack.pop()

                    # Record the end of the scope
                    self.scope[start_line_key]['line_num_end'] = line_begin
                    if lexeme.next() and lexeme.next().next() and lexeme.next().token() == 'Newline' and lexeme.next().next().token() != 'Indent':
                        self.scope[start_line_key]['column_num_end'] = lexeme.column_end()
                    # self.scope[start_line_key]['column_num_end'] = lexeme.column_end()
        # print("scope Lines ",self.scope)

    def record_conditional_scope(self):
        """
        Records the scope of conditional constructs (if, else, else-if) in Java.
        """
        if_tracker_stack = []
        self.conditional_scope = {}
        else_if_tracker = []
        curr_if = []

        for lexeme in self.file.lexer():
            if lexeme.token() not in ['Whitespace', 'Newline']:
                if not lexeme.ent():
                    continue
                control_flow_graph = lexeme.ent().freetext('CGraph')
                if control_flow_graph:
                    for parser in control_flow_graph.split(';'):
                        parser_nums = []
                        for x in parser.split(','):  # node_type, start_line, start_col, end_line, end_col
                            if x != '':
                                try:
                                    parser_nums.append(int(x))
                                except ValueError:
                                    parser_nums = []
                                    break
                        if not parser_nums or len(parser_nums) < 5:
                            continue

                        if parser_nums[0] == 5:  # Node type 5 corresponds to 'if' in Java
                            if parser_nums[1] not in else_if_tracker:
                                if_tracker_stack.append(parser_nums)
                                curr_if.append(parser_nums)
                                self.conditional_scope[parser_nums[1]] = {
                                    'if': {
                                        'line_num_begin': parser_nums[1],
                                        'column_num_begin': parser_nums[2],
                                        'line_num_end': parser_nums[3],
                                        'column_num_end': parser_nums[4]
                                    }
                                }

                        # Handle 'else' nodes
                        elif parser_nums[0] == 7 and (len(if_tracker_stack) or curr_if):  # Node type 7 for 'else'
                            if not len(curr_if):
                                curr_if.append(if_tracker_stack[-1])
                            else_if_tracker.append(parser_nums[1])
                            current = curr_if.pop()
                            if 'else' not in self.conditional_scope[current[1]]:
                                self.conditional_scope[current[1]]['else'] = [{
                                    'line_num_begin': parser_nums[1],
                                    'column_num_begin': parser_nums[2],
                                    'line_num_end': parser_nums[3],
                                    'column_num_end': parser_nums[4]
                                }]
                            else:
                                self.conditional_scope[current[1]]['else'].append({
                                    'line_num_begin': parser_nums[1],
                                    'column_num_begin': parser_nums[2],
                                    'line_num_end': parser_nums[3],
                                    'column_num_end': parser_nums[4]
                                })

                        # Handle 'endif' nodes
                        elif parser_nums[0] == 8 and len(curr_if):  # Node type 8 for 'endif'
                            current = curr_if.pop()
                            self.conditional_scope[current[1]]['endif'] = {
                                'line_num_begin': parser_nums[1],
                                'column_num_begin': parser_nums[2],
                                'line_num_end': parser_nums[3],
                                'column_num_end': parser_nums[4]
                            }
                            if len(if_tracker_stack):
                                if_tracker_stack.pop()


    def lexeme_matcher(self, lexeme, string, line_num, direction='next'):
        while lexeme:
            if lexeme.line_begin() == line_num:
                if lexeme.text() == string:
                    return True
            else:
                return False

            if direction == 'next':
                lexeme = lexeme.next()
            else:
                lexeme = lexeme.previous()


    def get_matched_lexeme(self, type, lexeme, string, line_num, direction='next'):
      matcher = lexeme.text() == string if type == 'string' else lexeme.token() == string
      while lexeme:
            if lexeme.line_begin() == line_num:
                if matcher:
                    return lexeme
            else:
                return None

            if direction == 'next':
                lexeme = lexeme.next()
            else:
                lexeme = lexeme.previous()

    def record_if_closure(self, lexeme, line_num):
      cond_key = str(line_num)
      self.conds[cond_key] = {
        'line_num_begin': line_num,
        'line_num_end': line_num,
        'column_num_begin': lexeme.column_begin(),
        'column_num_end': lexeme.column_begin(),
        'enclosing_brace_count': 0,
      }

      if_without_braces = False
      has_braces = False
      while lexeme and lexeme.line_begin() < self.method_lines[-1]:
        if lexeme.token() == 'Newline' and self.lexeme_matcher(lexeme, ')', lexeme.line_begin(), 'previous') and not has_braces:
          if_without_braces = True
          has_braces = False
        if if_without_braces and lexeme.text() == ';':
          self.conds[cond_key]['has_braces'] = False
          self.conds[cond_key]['line_num_end'] = lexeme.line_begin()
          self.conds[cond_key]['column_num_end'] = lexeme.column_end()
          break
        if lexeme.text() == '{' and not if_without_braces:
          has_braces = True
          self.conds[cond_key]['enclosing_brace_count'] += 1
          self.conds[cond_key]['has_braces'] = True
        if lexeme.text() == '}' and self.conds[cond_key]['enclosing_brace_count'] > 0 and not if_without_braces:
          self.conds[cond_key]['enclosing_brace_count'] -= 1
          if self.conds[cond_key]['enclosing_brace_count'] == 0:
            self.conds[cond_key]['line_num_end'] = lexeme.line_begin()
            self.conds[cond_key]['column_num_end'] = lexeme.column_end()
            break

        lexeme = lexeme.next()
    #   print("conds1",self.conds)
      
    def record_else_closure(self, lexeme):
        while lexeme and lexeme.line_begin() < self.method_lines[-1]:
            if lexeme.text() == 'else':
                else_key = lexeme.text() + '_' + str(lexeme.line_begin())
                lex_it = lexeme
                self.conds[else_key] = {}
                self.conds[else_key] = {
                'column_num_begin': lexeme.column_begin(),
                'column_num_end': lexeme.column_end(),
                'line_num_begin': lexeme.line_begin()
                }

                else_without_braces = False
                has_braces = False
                while lex_it and lex_it.line_begin() < self.method_lines[-1]:
                    if lex_it.token() != 'Whitespace':
                        if lex_it.text() == '{' and lex_it.previous().text() != '$':
                            has_braces = True
                            self.conds[else_key]['has_braces'] = True
                            else_without_braces = False

                        if lex_it.token() == 'Newline' and not has_braces:
                            else_without_braces = True
                            self.conds[else_key]['has_braces'] = False
                            matched_lexeme = self.get_matched_lexeme('string', lex_it.next(), ';', lex_it.line_end() + 1) or self.get_matched_lexeme('token', lex_it.next(), 'Newline', lex_it.line_end() + 1)
                            if matched_lexeme:
                                self.conds[else_key]['column_num_end'] = matched_lexeme.column_end() 
                                self.conds[else_key]['line_num_end'] = lex_it.line_end() + 1
                                break
                            lex_it = lex_it.next()
                        
                        if else_without_braces and (lex_it.text() == ';' or (lex_it.next() and lex_it.next().token() == 'Newline')):
                            self.conds[else_key]['column_num_end'] = lex_it.column_end() + 1
                            self.conds[else_key]['line_num_end'] = lex_it.line_end()
                            else_without_braces = False
                            self.conds[else_key]['has_braces'] = False
                            break

                        if lex_it.text() == '}' and lex_it.next().text() != '`' and not else_without_braces:
                            self.conds[else_key]['column_num_end'] = lex_it.column_end()
                            self.conds[else_key]['line_num_end'] = lex_it.line_end()
                            break

                        self.conds[else_key]['column_num_end'] = lex_it.column_end()
                        self.conds[else_key]['line_num_end'] = lex_it.line_end()

                    lex_it = lex_it.next()      
            lexeme = lexeme.next()
        # print("Conditional:",self.conds)  

    def record_loop_closure(self, lexeme, line_num):
        loop_key = str(line_num)
        self.loops[loop_key] = {
            'line_num_begin': line_num,
            'line_num_end': line_num,
            'enclosing_brace_count': 0
        }
        while lexeme and lexeme.line_begin() < self.method_lines[-1]:
            if lexeme.text() == '{':
                self.loops[loop_key]['enclosing_brace_count'] += 1
            if lexeme.text() == '}' and self.loops[loop_key]['enclosing_brace_count'] > 0:
                self.loops[loop_key]['enclosing_brace_count'] -= 1
                if self.loops[loop_key]['enclosing_brace_count'] == 0:
                    self.loops[loop_key]['line_num_end'] = lexeme.line_begin()
                    break
            lexeme = lexeme.next()


    def record_line_closure(self, lexeme, line_num):
        line_key = str(line_num)
        if line_key not in self.statement_closure:
            self.statement_closure[line_key] = []
            while lexeme and lexeme.line_begin() < (self.method_lines[-1] + 1) and lexeme.line_begin() > self.method_lines[0]:
                if lexeme.text() in ['{', '}', 'if', 'else', 'while', 'try', 'catch'] and lexeme.line_begin() == line_num:
                    del self.statement_closure[line_key]
                    break

                if lexeme.text() == ';':
                    self.statement_closure[line_key] = list(range(line_num, lexeme.line_begin() + 1))
                    break
                lexeme = lexeme.next()


    def analyze_closure(self):
        self.record_scope()
        self.record_conditional_scope()
        for line_num in self.method_lines:
            for lexeme in self.file.lexer():
                if lexeme.line_begin() == line_num:
                    if lexeme.token() not in ['Whitespace', 'Newline']:
                        if lexeme.token() == 'Keyword' and lexeme.text() in ['for', 'while']: # recording loops
                            self.record_loop_closure(lexeme, line_num)
                        elif lexeme.text() == 'if':
                            self.record_if_closure(lexeme, line_num)
                            self.record_else_closure(lexeme)
                    self.record_line_closure(lexeme, line_num)
        # print("statmentClosure",self.statement_closure)

    
    def _record_class_scope(self, lexeme, line_stack):
        while lexeme:
            if lexeme.text() == 'class' and lexeme.ent() and lexeme.ent().kindname() == 'Class':
                line_stack.add(lexeme.line_begin())  # Add the line where the class begins
                break
            # print("lexeme.text",lexeme.text())
            lexeme = lexeme.previous()

    def _record_method_scope(self, lexeme, line_stack):
        """
        Records the starting line of the method scope in Java.
        """
        while lexeme:
            # Look for the start of the method body '{' or method declaration ')'
            if lexeme.text() == '{' and lexeme.ent() and 'Method' in lexeme.ent().kindname():
                # Add the starting line of the method to the stack
                line_stack.add(lexeme.line_begin())
                break
            # If '(' is encountered, continue looking for the method declaration
            elif lexeme.text() == ')' and lexeme.ent() and 'Method' in lexeme.ent().kindname():
                # Trace backward to identify the complete method signature
                line_stack.add(lexeme.line_begin())
            lexeme = lexeme.previous()
    
    def get_related_var_lines(self, line_stack, analyzed_lines, show_use_by=False):
        related_line_stack = []
        while line_stack:
            pointer_line = line_stack.pop()
            # if pointer_line in analyzed_lines:
            #     print(pointer_line)
            #     continue
            variables = self.get_variable_entities(pointer_line)
            for var in variables:
                if var.library() == "Standard":
                    continue  # Skip standard library variables
                for reference in var.refs():
                    print('references',reference.kind())
                    current_line = reference.line()
                    if (
                        current_line < self.buggy_line_num and
                        current_line not in analyzed_lines and
                        current_line not in self.comment_lines and
                        reference.kind().longname() in REL_KIND 
                    ):  
                        related_line_stack.append(current_line)
            analyzed_lines.add(pointer_line)
            if len(analyzed_lines) > CONTEXT_WINDOW_LENGTH:
                print("exit")
                return analyzed_lines
            if not line_stack:
                line_stack = line_stack | set(related_line_stack)
                related_line_stack = []
        return analyzed_lines  
    
    def get_related_var_lines(self, line_stack, analyzed_lines, show_use_by=False):
        # Define priority order for reference kinds
        priority_order = [
            'Definein',
            'Define', 
            'Useby', 
            'Setby', 
            'Modifyby', 
            'Useby Partial'
        ]

        # Create a dictionary to store references by their priority
        priority_refs = {priority: set() for priority in priority_order}
        references = []
        related_line_stack = []
        while line_stack:
            pointer_line = line_stack.pop()
            variables = self.get_variable_entities(pointer_line)

            for var in variables:
                if var.library() == "Standard":
                    continue 
                for reference in var.refs():
                    references.append(reference)
                    current_line = reference.line()
                    if (
                        current_line < self.buggy_line_num and
                        current_line not in analyzed_lines and
                        current_line not in self.comment_lines and
                        reference.kind().longname() in REL_KIND 
                    ):  
                        related_line_stack.append(current_line)
            analyzed_lines.add(pointer_line)

            if not line_stack:
                line_stack = line_stack | set(related_line_stack)
                related_line_stack = []



        # Add lines to be analyzed in priority order
        for priority in priority_order:
            for line in sorted(priority_refs[priority]):
                if len(analyzed_lines) < CONTEXT_WINDOW_LENGTH:
                    analyzed_lines.add(line)
                else:
                    print(f"exit after reaching context limit at priority {priority}")
                    return analyzed_lines

        return analyzed_lines


    def get_variable_entities(self, line_number):
        """
        Retrieve all entities (e.g., variables, methods, fields) from a specific line in a Java file.
        """
        variables = []

        # Iterate through all lexemes in the file
        for lexeme in self.file.lexer():
            # Focus only on lexemes that start at the given line number

            if lexeme.line_begin() == line_number:
                # Process identifiers with associated entities
                # print("token: ",lexeme.text(),lexeme.token(),lexeme.ent(),line_number)
                if lexeme.token() == 'Identifier' and lexeme.ent():
                    entity = lexeme.ent()
                    kindname = entity.kindname()
                    variables.append(entity)
                    # print("entity: ",entity.name(), "kindname: ", kindname)


                    # For fields or class-level variables, add the parent entity (the class or enclosing scope)
                    if kindname == 'Field' and entity.parent():
                        variables.append(entity.parent())

                    self.is_skip = False

                    # Include methods for slicing calls
                    # if 'Method' in kindname:
                    #     variables.append(entity)
            
            # print(self.is_skip)

        return variables
    def is_within_loop(self, line_num):
        loop_lines = []
        for key,value in self.loops.items():
            if value.get('line_num_begin') and value.get('line_num_end') and line_num:
                if line_num >= int(value['line_num_begin']) and line_num <= int(value['line_num_end']): 
                    loop_lines.append((value['line_num_begin'], value['line_num_end']))
        return loop_lines


    def is_within_scope(self, line_num):
        scope_lines = []
        for key,value in self.scope.items():
            # print(value)
            if value.get('line_num_begin') and value.get('line_num_end') and line_num:
                if line_num >= int(value['line_num_begin']) and line_num <= int(value['line_num_end']):
                    scope_lines.append((value['line_num_begin'], value['line_num_end'], value['is_variable']))
        return scope_lines

    def is_within_conditional(self, line_num):
        cond_lines = []
        # print("conditional",self.conds)
        for key,value in self.conds.items():
            if value.get('line_num_begin') and value.get('line_num_end') and line_num:
                if line_num >= int(value['line_num_begin']) and line_num <= int(value['line_num_end']): 
                    cond_lines.append((value['line_num_begin'], value['line_num_end']))
                    if 'else' in key:
                        self.else_lines.add(value['line_num_begin'])
        return cond_lines
  
    def find_conditional_by_else(self, lines):
        """
        Updates the slice to include lines associated with 'else' blocks by tracing back to their corresponding 'if' blocks
        and adding any relevant conditional lines.
        """
        updated_lines = lines.copy()

        # Find lines that overlap with recorded 'else' lines
        common_lines_between_current_and_else_lines = self.else_lines.intersection(lines)

        for line_num in common_lines_between_current_and_else_lines:
            # Iterate through recorded conditional scopes
            for cond_type_line_map in self.conditional_scope.values():
                if 'else' in cond_type_line_map:
                    # Get the last 'else' block index
                    last_index = len(cond_type_line_map['else']) - 1
                    for idx, val in enumerate(cond_type_line_map['else']):
                        # Match the current line to an 'else' block
                        if val['line_num_begin'] == line_num:
                            # Find the corresponding 'if' block
                            start_if = cond_type_line_map['if']['line_num_begin']

                            # Add all lines from the 'if' block to the 'else' block
                            if start_if not in lines:
                                c = start_if
                                while c <= line_num:
                                    updated_lines.add(c)
                                    c += 1

                            # Include the 'endif' if it exists and this is the last 'else'
                            if idx == last_index and cond_type_line_map.get('endif'):
                                updated_lines.add(cond_type_line_map['endif']['line_num_begin'])

        return updated_lines

    def on_add_line(self, line_numbers):
        def _on_add(line_num):
            is_within_loop = self.is_within_loop(line_num)
            is_within_conditional = self.is_within_conditional(line_num)
            is_within_scope = self.is_within_scope(line_num)
            new_lines = set()

            if len(is_within_loop): # if a line is start of the loop, add the end of the loop (curly brace)
                for l in is_within_loop:
                    new_lines.add(l[0])
                    new_lines.add(l[1])
            if len(is_within_conditional): # if a line is start of the loop, add the end of the loop (curly brace)
                for l in is_within_conditional:
                    new_lines.add(l[0])
                    new_lines.add(l[1])
            if len(is_within_scope): # if a line is start of the scope, add the end of the scope (curly brace)
                for l in is_within_scope:
                    new_lines.add(l[0])
                    i = l[0]
                    if l[2]:
                        while i <= l[1]:
                            new_lines.add(i)
                            i += 1
                    else:
                        new_lines.add(l[1])
            # print("new_lines",new_lines)
            return new_lines
        
        if type(line_numbers) is set:
            updated_set = set()
            for l in line_numbers:
                updated_set = _on_add(l).union(updated_set)
            return updated_set
        else:
            return _on_add(line_numbers)
        
    def _get_outermost_parent(self, first_line):
        for lexeme in self.file.lexer():
            if lexeme.line_begin() == first_line and lexeme.token() not in ['Whitespace', 'Newline']:
                if lexeme.ent() and lexeme.ent().parent():
                    if lexeme.ent().parent().kindname() == 'File':
                        return None
                    elif lexeme.ent().parent().kindname() != 'File':
                        return lexeme.ent().parent().refs()[0].line()
                return None    

    def _get_object_beginning(self, line_number):
        for lexeme in self.file.lexer():
            if lexeme.line_begin() == line_number:
                if lexeme.token() not in ['Whitespace', 'Newline']:
                    if lexeme.text() == '.' and lexeme.previous().token() == 'Whitespace':
                        return self._get_object_beginning(line_number - 1)
                    else:
                        return line_number 
            
    def get_statements_lines(self, lines):
        print("lines",lines)
        # print(self.scope)
        # print(self.has_function_call)
        # print("variables",self.function_variables)
        line_to_col_map = {}
        updated_lines = lines.copy()
        for line_num in lines:
            key = str(line_num)
            if self.has_function_call and line_num in self.function_variables:
                if key in self.scope and self.scope[key]:
                    # print(self.scope[key])
                    #check-this
                    i = line_num
                    while i < self.scope[key].get("line_num_begin"):
                        print("calls while loops")
                        updated_lines.add(i)
                        i += 1
            
            updated_lines = self.on_add_line(line_num).union(updated_lines)
            # print(self.conds)
            if key in self.conds and self.conds[key]['line_num_end']: # if a line is start of a conditional, add the end of the loop (curly brace)
                # print("before",updated_lines)
                line = self.conds[key]['line_num_end']
                updated_lines.add(line)
                # print("after",updated_lines)
                if self.conds[key].get('column_num_begin') and line not in line_to_col_map: # this takes care of the column end
                    line_to_col_map[line] = {
                        'column_num_begin': self.conds[key]['column_num_begin'],
                        'column_num_end': self.conds[key]['column_num_end']
                    }
                    # print("line", line)
            if key in self.scope:
                print("in scope",key)
            if key in self.scope and self.scope[key] is not None and 'line_num_end' in self.scope[key]: # if a line falls within a method scope, add the end of the line to the list
                line = self.scope[key]['line_num_end']
                updated_lines.add(line)
                print("lined", line)
                if self.scope[key].get('column_num_begin') and self.scope[key].get('column_num_end') and line not in line_to_col_map: # this takes care of the column end
                    line_to_col_map[line] = {
                    'column_num_begin': self.scope[key]['column_num_begin'],
                    'column_num_end': self.scope[key]['column_num_end']
                    }
                 # check if the lines fall within an if block, then add the else blocks too
                #check-this
            for i in self.conds:
                print("ssss",i)
                block_start = int(i.split('_')[-1]) if i.startswith('else_') else int(i)
                # print(block_start,line_num)
                if int(line_num) >= block_start and int(line_num) <= int(self.conds[i]['line_num_end']):
                    # print(line_num,int(self.conds[i]['line_num_end'] ))
                    updated_lines.add(block_start)
                    updated_lines.add(self.conds[i]['line_num_end'])
                    if self.conds[i].get('column_num_end'):
                        if block_start in line_to_col_map:
                            del line_to_col_map[block_start]
                        else:
                            line_to_col_map[self.conds[i]['line_num_end']] = {
                            'column_num_begin': self.conds[i]['column_num_begin'],
                            'column_num_end': self.conds[i]['column_num_end']
                            }

            # this takes care of single line statement end
            for statement_continuations in self.statement_closure.values():
                if line_num in statement_continuations:
                    for s in statement_continuations:
                        updated_lines.add(s)
                        updated_lines = self.on_add_line(s).union(updated_lines)
            # print("updated2",updated_lines)
        updated_lines = set(sorted([i for i in updated_lines if i]))
        if int(self.method_start_line_num) in updated_lines:
            updated_lines.add(self.method_lines[-1])
            updated_lines = self.on_add_line(self.method_lines[-1]).union(updated_lines)
        
        # this takes care of object start
        start_of_line = None
        for line_num in list(updated_lines.copy()):
            for lexeme in self.file.lexer():
                if lexeme.line_begin() == line_num:
                    if lexeme.text() == '.' and lexeme.previous().token() == 'Whitespace':
                        start_of_line = self._get_object_beginning(line_num - 1)

                        if start_of_line:
                            updated_lines.add(start_of_line)
                            updated_lines = self.on_add_line(start_of_line).union(updated_lines)
                            start_of_line = None

        parent_line = self._get_outermost_parent(min(updated_lines))
        if parent_line and self.scope.get(str(parent_line)):
            updated_lines.add(parent_line)
            end_line = self.scope[str(parent_line)].get('line_num_end')
            if end_line:
                updated_lines.add(end_line)
        lines_with_related_vars = self.get_related_var_lines(set(updated_lines), set(updated_lines), show_use_by=True)
        unified_lines = self.on_add_line(lines_with_related_vars.difference(updated_lines)).union(lines_with_related_vars)
        final_lines = self.find_conditional_by_else(unified_lines)
        updated_lines = sorted([i for i in final_lines if i])
        print("cols",line_to_col_map)
        self.complete_scope(updated_lines,line_to_col_map)
        return updated_lines,line_to_col_map

    def complete_scope(self, lines, line_to_col_map):
        for line in lines:
            line = str(line)
            if line not in line_to_col_map:
                if line in self.scope and self.scope[line] is not None and 'line_num_end' in self.scope[line] and not (line in self.else_lines or line in self.conditional_scope or line in self.conds):
                    end_line = self.scope[line].get('line_num_end')
                    if end_line and end_line in self.scope:
                        line_to_col_map[end_line] = {
                    'column_num_begin': self.scope[line]['column_num_begin'],
                    'column_num_end': self.scope[line]['column_num_end']
                    }

    def run(self, file_obj=None, root_path=None, dual_slice=False, js_file_type=None):
        line_stack = set()
        analyzed_lines = set()
        variables = self.get_variable_entities(self.buggy_line_num)
        # if self.is_skip:
        #     # print("skipped",self.buggy_line_num)
        #     return [],{}
        for var in variables:
            if "Method" in var.kindname():
                self.has_function_call = True  
            if var.parent() and ("constructor" in var.parent().name() or "Class" in var.parent().kindname()): # If its a function within a class, record the parent scope
                # print("method",var.parent().name(),var.parent().kindname(),var)
                lexeme = var.lexer().lexeme(var.ref().line(), var.ref().column())
                self._record_class_scope(lexeme, line_stack)
                self._record_method_scope(lexeme, line_stack)
            if var.library() == "Standard":
                continue
            # print(var.refs)
            checked_lines = set()
            for reference in var.refs():
                # print(var,reference.line(),reference.kind())
                current_line = reference.line()
                if current_line in checked_lines:
                    continue
                if var.parent():
                    condition = current_line < self.buggy_line_num and current_line > self.method_start_line_num and current_line not in analyzed_lines and var.parent().name() != "System" and reference.kind().longname() in REL_KIND
                else:
                    condition = current_line < self.buggy_line_num and current_line > self.method_start_line_num and current_line not in analyzed_lines  and reference.kind().longname() in REL_KIND
                if condition:
                    line_stack.add(current_line)
                checked_lines.add(current_line)
            del checked_lines
        # print(line_stack)
        analyzed_lines.add(self.buggy_line_num)
        if not len(line_stack):
            # return the buggy line as context
            return [self.buggy_line_num],{}
        analyzed_lines = self.get_related_var_lines(line_stack, analyzed_lines)
        # print(analyzed_lines)
        del line_stack
        self.analyze_closure()
        return self.get_statements_lines(set([a for a in analyzed_lines if a is not None]))

# def skip_context():


def process_single_line(project_path, file_name, line_number):
  db = understand.open(project_path)
  buggy_line_num = int(line_number)
  file = db.lookup(file_name)[0]
  FILE = file
  if file:
     print("exists")
  
  bs = BackwardSlicing(db, file, buggy_line_num)
  context_lines, line_to_col_map = bs.run()
  print("context lines",context_lines)
  print("line to col",line_to_col_map)
  statements = []
  for line_num in context_lines:
    statement = ''
    for lexeme in file.lexer():
      if lexeme.line_begin() == line_num:
        if lexeme.token() not in ['Newline']:
          if line_num in line_to_col_map:
            if lexeme.column_end() <= line_to_col_map[line_num]['column_num_end']:
              statement += lexeme.text()
          else:
            statement += lexeme.text()

    statements.append(statement.rstrip())
  db.close()

  return statements,context_lines


def process_multiple_lines(project_path, file_name, line_numbers):
    db = understand.open(project_path)
    buggy_lines = sorted(line_numbers, reverse=True)
    file = db.lookup(file_name)[0]
    statements = []
    multi_context_lines = []
    multi_line_to_col_map = {}

    for line in buggy_lines:
      if line in multi_context_lines:
         continue
      bs = BackwardSlicing(db, file, line)
      context_lines, line_to_col_map = bs.run()
    #   print("ccc",context_lines)
      multi_context_lines.extend(context_lines)
      multi_line_to_col_map.update(line_to_col_map)

    # print("line_to_Col:",multi_line_to_col_map)
    multi_context_lines = sorted(list(set(multi_context_lines)))
    # print("multi2",multi_context_lines)
    for line_num in multi_context_lines:
      statement = ''
      for lexeme in file.lexer():
        if lexeme.line_begin() == line_num:
          if lexeme.token() not in ['Newline']:
            if line_num in multi_line_to_col_map:
              if lexeme.column_end() <= multi_line_to_col_map[line_num]['column_num_end']:
                statement += lexeme.text()
            else:
              statement += lexeme.text()

      statements.append(statement.rstrip())
    db.close()
    return statements,multi_context_lines

# use this if backward slicing is needed

# if __name__ == "__main__":
#     project_und_path = ""
#     file_name = ""
#     line_number = 
#     line_numbers = 
#     start_time = time.time() 
#     statements,context_lines = process_single_line(project_und_path,file_name,line_number)
#     # statements,context_lines = process_multiple_lines(project_und_path,file_name,line_numbers)
   

#     for line in statements:
#         print(line)
#     # print("context",context_lines)