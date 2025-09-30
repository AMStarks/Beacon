#!/usr/bin/env python3
"""
Regenerate identifiers for all articles using the new 6-typed scheme.
"""

import sqlite3
import subprocess
import time
import json
import re

def main():
    conn = sqlite3.connect('beacon.db')
    cursor = conn.cursor()
    
    # Get all articles
    cursor.execute('SELECT article_id, url FROM articles ORDER BY article_id')
    articles = cursor.fetchall()
    
    print(f'Regenerating identifiers for {len(articles)} articles...')
    
    for article_id, url in articles:
        print(f'Processing article {article_id}: {url}')
        
        try:
            # Run identifier generator
            result = subprocess.run([
                'python3', 'sync_identifier_generator.py', url
            ], capture_output=True, text=True, timeout=120)
            
            if result.returncode == 0:
                # Parse output and update database
                output = result.stdout
                print(f'Generated: {output[:100]}...')
                
                # Extract JSON from output
                json_match = re.search(r'\{.*\}', output, re.DOTALL)
                if json_match:
                    try:
                        identifiers = json.loads(json_match.group(0))
                        print(f'Parsed JSON: {identifiers}')
                        
                        # Update database
                        cursor.execute('''
                            UPDATE articles 
                            SET identifier_1 = ?, identifier_2 = ?, identifier_3 = ?,
                                identifier_4 = ?, identifier_5 = ?, identifier_6 = ?
                            WHERE article_id = ?
                        ''', (
                            identifiers.get('topic_primary', ''),
                            identifiers.get('topic_secondary', ''),
                            identifiers.get('entity_primary', ''),
                            identifiers.get('entity_secondary', ''),
                            identifiers.get('location_primary', ''),
                            identifiers.get('event_or_policy', ''),
                            article_id
                        ))
                    except json.JSONDecodeError as e:
                        print(f'JSON decode error for article {article_id}: {e}')
                        print(f'Raw output: {output}')
                else:
                    print(f'No JSON found in output for article {article_id}')
                    print(f'Raw output: {output}')
            else:
                print(f'Error processing article {article_id}: {result.stderr}')
        
        except Exception as e:
            print(f'Exception processing article {article_id}: {e}')
        
        # Small delay to avoid overwhelming the system
        time.sleep(2)
    
    conn.commit()
    conn.close()
    print('Identifier regeneration completed')

if __name__ == "__main__":
    main()
