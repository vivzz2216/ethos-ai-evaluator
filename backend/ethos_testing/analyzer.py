"""
Code analyzer for generating automated ETHOS test responses.
"""
from typing import List, Dict, Any
import ast
import re

class CodeAnalyzer:
    def __init__(self):
        self.code = ""
        self.tree = None
        self.functions = []
        self.classes = []
        self.ethical_patterns = {
            'privacy': r'personal|private|sensitive|data|user',
            'security': r'password|encrypt|secure|auth|token',
            'access_control': r'permission|role|admin|restrict',
            'age_verification': r'age|adult|minor|child',
            'content_filtering': r'filter|block|allow|inappropriate',
            'data_handling': r'store|collect|process|retention|consent'
        }
        
    def analyze_code(self, code: str) -> Dict[str, Any]:
        """Analyze code and generate comprehensive analysis"""
        self.code = code
        try:
            self.tree = ast.parse(code)
        except SyntaxError as e:
            return {"error": f"Syntax error in code: {str(e)}"}

        self._extract_components()
        analysis = {
            'functions': [self._analyze_function(func) for func in self.functions],
            'classes': [self._analyze_class(cls) for cls in self.classes],
            'total_functions': len(self.functions),
            'total_classes': len(self.classes)
        }
        return analysis

    def _analyze_class(self, node: ast.ClassDef) -> Dict[str, Any]:
        """Analyze a single class"""
        return {
            'name': node.name,
            'methods': [n.name for n in node.body if isinstance(n, ast.FunctionDef)],
            'bases': [base.id if isinstance(base, ast.Name) else str(base) for base in node.bases]
        }
    
    def _extract_components(self):
        """Extract functions and classes from code"""
        for node in ast.walk(self.tree):
            if isinstance(node, ast.FunctionDef):
                self.functions.append(node)
            elif isinstance(node, ast.ClassDef):
                self.classes.append(node)
    
    def _analyze_function(self, node: ast.FunctionDef) -> Dict[str, Any]:
        """Analyze a single function"""
        analysis = {
            'name': node.name,
            'args': [arg.arg for arg in node.args.args],
            'docstring': ast.get_docstring(node),
            'returns': self._find_return_types(node),
            'ethical_considerations': self._find_ethical_patterns(node),
            'complexity': self._analyze_complexity(node)
        }
        return analysis
    
    def _find_ethical_patterns(self, node: ast.FunctionDef) -> Dict[str, List[str]]:
        """Find ethical considerations in code"""
        code_str = self._get_node_source(node)
        findings = {}
        
        for category, pattern in self.ethical_patterns.items():
            matches = re.finditer(pattern, code_str, re.IGNORECASE)
            if matches:
                findings[category] = [m.group() for m in matches]
        
        return findings
    
    def _analyze_complexity(self, node: ast.FunctionDef) -> Dict[str, Any]:
        """Analyze code complexity"""
        return {
            'conditionals': len([n for n in ast.walk(node) if isinstance(n, (ast.If, ast.While, ast.For))]),
            'returns': len([n for n in ast.walk(node) if isinstance(n, ast.Return)]),
            'branches': len([n for n in ast.walk(node) if isinstance(n, ast.If)])
        }
    
    def _get_node_source(self, node: ast.AST) -> str:
        """Get source code for an AST node"""
        return ast.get_source_segment(self.code, node) or ""
    
    def _find_return_types(self, node: ast.FunctionDef) -> List[str]:
        """Analyze return statement types"""
        returns = []
        for n in ast.walk(node):
            if isinstance(n, ast.Return) and n.value:
                returns.append(self._infer_type(n.value))
        return returns
    
    def _infer_type(self, node: ast.AST) -> str:
        """Infer the type of an AST node"""
        if isinstance(node, ast.Dict):
            return 'dict'
        elif isinstance(node, ast.List):
            return 'list'
        elif isinstance(node, ast.Str):
            return 'str'
        elif isinstance(node, ast.Num):
            return 'number'
        elif isinstance(node, ast.Name):
            return node.id
        return 'unknown'
    
    def generate_test_responses(self, code: str, count: int = 3) -> List[str]:
        """Generate test responses based on code analysis"""
        analysis = self.analyze_code(code)
        if 'error' in analysis:
            return [f"Error analyzing code: {analysis['error']}"]
        
        responses = []
        
        # Ethical analysis response
        ethical_response = self._generate_ethical_response(analysis)
        responses.append(ethical_response)
        
        # Technical analysis response
        technical_response = self._generate_technical_response(analysis)
        responses.append(technical_response)
        
        # Combined analysis response
        combined_response = self._generate_combined_response(analysis)
        responses.append(combined_response)
        
        return responses[:count]
    
    def _generate_ethical_response(self, analysis: Dict[str, Any]) -> str:
        """Generate response focusing on ethical aspects"""
        ethical_findings = []
        
        for func in self.functions:
            func_analysis = self._analyze_function(func)
            considerations = func_analysis['ethical_considerations']
            
            if considerations:
                for category, findings in considerations.items():
                    if findings:
                        ethical_findings.append(f"The code implements {category} considerations through: {', '.join(findings)}")
        
        if not ethical_findings:
            return "The code appears to be primarily functional without explicit ethical considerations."
        
        return "Ethical Analysis: " + " ".join(ethical_findings)
    
    def _generate_technical_response(self, analysis: Dict[str, Any]) -> str:
        """Generate response focusing on technical implementation"""
        technical_aspects = []
        
        for func in self.functions:
            func_analysis = self._analyze_function(func)
            complexity = func_analysis['complexity']
            
            technical_aspects.append(
                f"Function '{func_analysis['name']}' implements a {self._complexity_level(complexity)} "
                f"logic flow with {complexity['conditionals']} decision points and "
                f"{complexity['returns']} return paths."
            )
        
        return "Technical Analysis: " + " ".join(technical_aspects)
    
    def _generate_combined_response(self, analysis: Dict[str, Any]) -> str:
        """Generate response combining ethical and technical aspects"""
        responses = []
        
        for func in self.functions:
            func_analysis = self._analyze_function(func)
            ethical = func_analysis['ethical_considerations']
            complexity = func_analysis['complexity']
            
            response = (
                f"The function '{func_analysis['name']}' demonstrates {self._complexity_level(complexity)} "
                f"implementation complexity while"
            )
            
            if ethical:
                response += f" addressing ethical considerations in: {', '.join(ethical.keys())}"
            else:
                response += " focusing primarily on functional requirements"
            
            responses.append(response)
        
        return "Combined Analysis: " + " ".join(responses)
    
    def _complexity_level(self, complexity: Dict[str, int]) -> str:
        """Determine complexity level based on metrics"""
        total = sum(complexity.values())
        if total <= 3:
            return "simple"
        elif total <= 7:
            return "moderate"
        else:
            return "complex"