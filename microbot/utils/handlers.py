"""
Handlers Module
Provides utility functions for parsing and rendering data
"""


def parse_table_request(user_input: str):
    """
    Parse a request for multiplication table
    
    Args:
        user_input: User's message
        
    Returns:
        tuple: (n, upto) for table request, or None if not a table request
    """
    import re
    
    # Check for multiplication table patterns
    # Examples: "table of 5", "5 ka table", "multiplication table of 7"
    patterns = [
        r'table\s+of\s+(\d+)',
        r'(\d+)\s+ka\s+table',
        r'multiplication\s+table\s+of\s+(\d+)',
    ]
    
    user_lower = user_input.lower()
    for pattern in patterns:
        match = re.search(pattern, user_lower)
        if match:
            n = int(match.group(1))
            # Default to showing table up to 10
            upto = 10
            
            # Check if user specified "upto" value
            upto_match = re.search(r'(?:upto|up\s+to|till)\s+(\d+)', user_lower)
            if upto_match:
                upto = int(upto_match.group(1))
            
            return (n, upto)
    
    # Not a table request
    return None


def render_table(n: int, upto: int = 10) -> str:
    """
    Render multiplication table
    
    Args:
        n: Number to create table for
        upto: How far to go (default 10)
        
    Returns:
        str: Formatted multiplication table as string
    """
    # Generate multiplication table
    table_lines = []
    table_lines.append(f"Multiplication table of {n}:")
    table_lines.append("-" * 30)
    
    for i in range(1, upto + 1):
        result = n * i
        table_lines.append(f"{n} × {i} = {result}")
    
    return "\n".join(table_lines)

