import sys
import os
from setPath import understand
import backwardSlicer
import dualSlicer



def traverse(project_path,context_lines,file,file_name):

    db = understand.open(project_path)
    file_names = [os.path.basename(file.longname()) for file in db.ents("File") if not file.library() and file.longname().endswith((".java"))]
    dependent_files = {}
    dependent_file_name = ""
    dependent_lines = []
    
    for lexeme in file.lexer():
        if lexeme.line_begin() in context_lines:
            if lexeme.ent():
                for ref in lexeme.ent().refs():
                    dependent_file = str(ref.file())
                    if dependent_file in file_names and str(ref.file()) != file_name:
                        
                        if str(ref.kind()) == "Begin" or str(ref.kind()) == "Define":
                            if dependent_file not in dependent_files:
                                dependent_files[dependent_file] = []
                            dependent_files[dependent_file].append(ref.line())
                        
    if dependent_files:
        dependent_file_name = max(dependent_files, key=lambda k: len(dependent_files[k]))
        dependent_lines = list(set(dependent_files[dependent_file_name]))
    else:
        return None,None,None
    statements,context_lines = backwardSlicer.process_multiple_lines(project_path=project_path,file_name=dependent_file_name,line_numbers=dependent_lines)

    return statements,context_lines,dependent_file_name
  
def process_single_line(project_und_path,file_name,line_number):
   statements_original,context_lines_original = dualSlicer.process_single_line(project_und_path,file_name,line_number)
   db = understand.open(project_und_path)
   files = db.lookup(file_name)
   file = None
   for f in files:
            if os.path.basename(f.longname()) == file_name:
                file = f
                break
   if file:
        pass
   else:
        print(f"File {file_name} not found in the project.")
        db.close()
        return

   main_file_path = file.longname()
   try:
        statements_dependent,context_lines_dependent,dependent_file_name = traverse(project_und_path,context_lines_original,file,file_name)
        if  statements_dependent and context_lines_dependent and dependent_file_name:
            statements_original.extend(statements_dependent)
            dependent_file = db.lookup(dependent_file_name)[0]
            dependent_file_path = dependent_file.longname()
            context_lines_original.extend(context_lines_dependent)
        else: 
            return statements_original,context_lines_original,main_file_path,None,None,None
   except Exception as e:
        print(f"🚨 Error in {file_name}: {e}")
        return None
   return statements_original,context_lines_original,main_file_path,statements_dependent,context_lines_dependent,dependent_file_path

def process_multiple_lines(project_und_path,file_name,line_numbers):
   statements_original,context_lines_original = dualSlicer.process_multiple_lines(project_und_path,file_name,line_numbers)

   db = understand.open(project_und_path)
   files = db.lookup(file_name)
   file = None
   for f in files:
            if os.path.basename(f.longname()) == file_name:
                file = f
                break
   if file:
        pass
   else:
        print(f"File {file_name} not found in the project.")
        db.close()
        return
   main_file_path = file.longname()
   try:
        statements_dependent,context_lines_dependent,dependent_file_name = traverse(project_und_path,context_lines_original,file,file_name)
        if  statements_dependent and context_lines_dependent and dependent_file_name:
            statements_original.extend(statements_dependent)
            dependent_file = db.lookup(dependent_file_name)[0]
            dependent_file_path = dependent_file.longname()
            context_lines_original.extend(context_lines_dependent)
        else: 
            return statements_original,context_lines_original,main_file_path,None,None,None
   except Exception as e:
        print(f"🚨 Error in {file_name}: {e}")
        return None
   return statements_original,context_lines_original,main_file_path,statements_dependent,context_lines_dependent,dependent_file_path
   
def process_dependent_files(multiple_files,project_und_path):
    final_statements,final_context_lines = [],[]
    for dependent_file in multiple_files:
      file_name = str(dependent_file)
      lines = multiple_files[dependent_file][0]
      statements,context_lines = backwardSlicer.process_multiple_lines(project_path=project_und_path,file_name=file_name,line_numbers=lines)
      
      final_statements.extend(statements)
      final_context_lines.extend(context_lines)
    
    # for line in final_statements:
    #    print(line)
    

if __name__ == "__main__":

    # Expect at least: multiFile.py <project.und> <FileName.java> <line1> [<line2> ...]
    if len(sys.argv) < 4:
        print("Usage: python multiFile.py <project.und> <FileName.java> <line1> [<line2> ...]")
        sys.exit(1)

    # 1) Pull in the arguments
    project_und_path = sys.argv[1]
    file_name        = sys.argv[2]
    line_numbers     = [int(x) for x in sys.argv[3:]]

    # 2) Call your slicer
    result = process_multiple_lines(project_und_path, file_name, line_numbers)
    if not result:
        sys.exit(1)

    (statements_original,
     context_lines_original,
     main_file_path,
     statements_dependent,
     context_lines_dependent,
     dependent_file_path) = result

    # 3) Print the original statements
    for stmt in statements_original:
        print(stmt)

    # 4) Print a marker so your extension can split out the context
    print("---CONTEXT---")

    # 5) Print the context lines
    for ctx in context_lines_original:
        print(ctx)
    
