import os
import re
from flask import Flask, render_template, request, Response
from lxml import etree
from xml.sax.saxutils import escape

def xml_value(value):
    return escape(value, {'"': "&quot;", "'": "&apos;"})

# Create an instance of the Flask application
app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 128 * 1024

@app.errorhandler(413)
def too_large(error):
    return 'Form exceeds the size limit.', 413

@app.get('/health')
def health():
    return {'status': 'ok'}

# Define the path to your XML template
XML_TEMPLATE_PATH = os.path.join(os.path.dirname(__file__), 'base_xml', 'consent_template.xml')

@app.route('/')
def index():
    """Serves the main HTML page."""
    return render_template('index.html')

@app.route('/generate', methods=['POST'])
def generate_xml():
    """
    Handles the form submission, modifies the XML as plain text,
    and returns the new file for download.
    """
    try:
        # --- 1. PARSE XML ONCE TO CREATE LOOKUP MAPS (READ-ONLY) ---
        parser = etree.XMLParser(recover=True, resolve_entities=False, load_dtd=False, no_network=True)
        tree = etree.parse(XML_TEMPLATE_PATH, parser)
        
        # Build Master List of Countries (Preserving Order for Logic)
        # Format: [{'code': 'DE', 'name': 'Germany'}, ...]
        master_country_list = []
        for row in tree.xpath("//radio[@label='DM_Country']/row"):
            # Ensure we don't grab empty or malformed rows
            if row.get('label'):
                master_country_list.append({'code': row.get('label'), 'name': row.text})
            
        # Map for POC Script generation
        country_to_code_map = {item['name']: item['code'] for item in master_country_list}
        
        poc_to_label_map = {
            row.text: row.get('label')
            for row in tree.xpath("//radio[@label='hName_GDPR']/row")
        }

        # --- 2. READ THE ENTIRE TEMPLATE FILE INTO A STRING ---
        with open(XML_TEMPLATE_PATH, 'r', encoding='utf-8') as f:
            xml_content_string = f.read()

        # --- 3. GET DATA FROM THE WEB FORM ---
        values = {}
        for field, limit in [('project_name', 200), ('project_number', 80), ('study_purpose', 2000)]:
            value = request.form.get(field, '').strip()
            if not value or len(value) > limit or any(ord(ch) < 32 for ch in value):
                return 'Please supply valid project details within the field limits.', 400
            values[field] = xml_value(value)
        project_name = values['project_name']
        project_number = values['project_number']
        study_purpose = values['study_purpose']
        seen = set()
        for i in range(1, 6):
            country = request.form.get(f'country{i}', '').strip()
            code = request.form.get(f'country_code{i}', '').strip().upper()
            poc = request.form.get(f'poc{i}', '')
            if not country and not code and not poc:
                continue
            if not country or len(country) > 100 or any(ord(ch) < 32 for ch in country):
                return 'Enter a valid country name.', 400
            resolved = code or country_to_code_map.get(country)
            if not resolved or not re.fullmatch(r'[A-Z][A-Z0-9_]{1,9}', resolved):
                return 'Use a valid country code (2–10 letters, digits or underscores, starting with a letter).', 400
            if resolved in seen or poc not in poc_to_label_map:
                return 'Select a valid contact and use each country code only once.', 400
            seen.add(resolved)
        if not seen:
            return 'Select at least one country and contact.', 400
        
        # --- DETERMINE USER SELECTIONS & ROWS TO KEEP ---
        user_selected_rows = []
        
        for i in range(1, 6):
            c_name = request.form.get(f'country{i}', '').strip()
            c_custom_code = request.form.get(f'country_code{i}')
            
            if c_name:
                # Determine Code
                code = None
                if c_custom_code:
                    code = c_custom_code.upper().strip()
                elif c_name in country_to_code_map:
                    code = country_to_code_map[c_name]
                
                if code:
                    # Store dict for XML row generation
                    user_selected_rows.append({'code': code, 'name': c_name})

        # --- APPLY FILTERING LOGIC (Minimum 2 Rows) ---
        final_rows_to_write = []

        if len(user_selected_rows) >= 2:
            # CASE A: Multi-country -> Keep only selected
            final_rows_to_write = user_selected_rows
            
        elif len(user_selected_rows) == 1:
            # CASE B: Single Country -> Keep Selected + Next (Wrap-around)
            selected_item = user_selected_rows[0]
            final_rows_to_write.append(selected_item)
            
            # Find index in master list
            current_index = -1
            for idx, item in enumerate(master_country_list):
                if item['code'] == selected_item['code']:
                    current_index = idx
                    break
            
            if current_index != -1:
                # Found in master list: Get next index with wrap-around
                next_index = (current_index + 1) % len(master_country_list)
                final_rows_to_write.append(master_country_list[next_index])
            else:
                # New Country (not in master): Add first country from master as buffer
                if master_country_list:
                    final_rows_to_write.append(master_country_list[0])
        
        # --- GENERATE NEW XML ROWS STRING ---
        # Format: Start with \n and use 4 spaces indentation
        new_rows_string = ""
        for item in final_rows_to_write:
            new_rows_string += f'\n    <row label="{item["code"]}">{xml_value(item["name"])}</row>'

        # --- 4. PERFORM MODIFICATIONS USING STRING REPLACEMENT ---

        # A) Modify Project Details
        xml_content_string = xml_content_string.replace(
            '<row label="r1">Project Number - PN12345</row>',
            f'<row label="r1">{project_number}</row>'
        )
        xml_content_string = xml_content_string.replace(
            '<row label="r2">Consent_Project_Template</row>',
            f'<row label="r2">{project_name}</row>'
        )
        
        # Replace Subject Line
        xml_content_string = xml_content_string.replace(
            '<res label="subjectLine_Interviewer">Completed Consent_Project_Template study</res>',
            f'<res label="subjectLine_Interviewer">Completed {project_name} study</res>'
        )

        # B) Modify Survey "Alt" Tag
        xml_content_string = xml_content_string.replace(
            'alt="CONSENT ONLY TEMPLATE"',
            f'alt="{project_number} - {project_name}"'
        )
        
        # C) Modify Study Purpose in Question S0
        if study_purpose:
            xml_content_string = xml_content_string.replace(
                'discuss Name of the project', 
                study_purpose
            )
            
        # --- REPLACE COUNTRY LISTS IN XML (Safe Logic) ---
        
        def replace_rows_in_radio(content, label, new_rows_str):
            # 1. Isolate the specific Radio Block (Non-Greedy match)
            block_pattern = re.compile(r'(<radio\s+[^>]*label="' + label + r'"[^>]*>)([\s\S]*?)(</radio>)')
            
            match = block_pattern.search(content)
            if match:
                start_tag = match.group(1)
                body = match.group(2)
                end_tag = match.group(3)
                
                # 2. Inside the body, replace the chunk of <row> tags
                rows_pattern = r'<row\s+label=[\s\S]*</row>'
                new_body = re.sub(rows_pattern, lambda match: new_rows_str, body)
                
                # 3. Reassemble and replace in original content
                new_block = start_tag + new_body + end_tag
                content = content.replace(match.group(0), new_block)
                
            return content

        # Apply replacement to DM_Country
        xml_content_string = replace_rows_in_radio(xml_content_string, "DM_Country", new_rows_string)
        
        # Apply replacement to vCountry
        xml_content_string = replace_rows_in_radio(xml_content_string, "vCountry", new_rows_string)
        
        # D) Handle Optional Clause Toggles
        if not request.form.get('audio_recording'):
            pattern = r'\s*<radio\s+label="S2".*?</radio>\s*<suspend/>\s*<term\s+label="te2".*?</term>\s*<suspend/>'
            xml_content_string = re.sub(pattern, "", xml_content_string, flags=re.DOTALL)

        if not request.form.get('re_contact'):
            pattern_s3 = r'\s*<radio\s+label="S3".*?</radio>\s*<suspend/>'
            xml_content_string = re.sub(pattern_s3, "", xml_content_string, flags=re.DOTALL)
            
        if not request.form.get('adverse_events'):
            pattern_ae = r'\s*<radio\s+label="AdverseEvents".*?</radio>\s*<suspend/>'
            xml_content_string = re.sub(pattern_ae, "", xml_content_string, flags=re.DOTALL)
            
        # E) Email Logic REMOVED (Always ON in Template)

        # F) Dynamically Generate and Replace the POC Script
        generated_script_lines = []
        
        for i in range(1, 6):
            country_name = request.form.get(f'country{i}', '').strip()
            poc_name = request.form.get(f'poc{i}')
            c_custom_code = request.form.get(f'country_code{i}')

            if country_name and poc_name:
                country_code = None
                if c_custom_code:
                    country_code = c_custom_code.upper().strip()
                elif country_name in country_to_code_map:
                    country_code = country_to_code_map[country_name]

                poc_label = poc_to_label_map.get(poc_name)

                if country_code and poc_label:
                    script_block = (
                        f"if DM_Country.{country_code}:\n"
                        f"\thName_GDPR.val = hName_GDPR.{poc_label}.index\n"
                        f"\thPipeDetails_GDPR.val = hPipeDetails_GDPR.{poc_label}.index"
                    )
                    generated_script_lines.append(script_block)
        
        placeholder_script = (
            "#if DM_Country.AE:\n"
            "#\thName_GDPR.val = hName_GDPR.r1.index\n"
            "#\thPipeDetails_GDPR.val = hPipeDetails_GDPR.r1.index"
        )
        
        final_generated_script = "\n\n".join(generated_script_lines)
        xml_content_string = xml_content_string.replace(placeholder_script, final_generated_script)

        # Validate structure while tolerating Decipher's unbound attribute prefixes.
        output_parser = etree.XMLParser(recover=True, resolve_entities=False, load_dtd=False, no_network=True)
        generated_root = etree.fromstring(xml_content_string.encode('utf-8'), output_parser)
        structural_errors = [e for e in output_parser.error_log
                             if e.level_name in ('ERROR', 'FATAL') and e.domain_name != 'NAMESPACE']
        if generated_root is None or structural_errors:
            raise ValueError('Generated XML has invalid structure')

        # --- 5. PREPARE AND RETURN THE FINAL STRING FOR DOWNLOAD ---
        return Response(
            xml_content_string,
            mimetype='application/xml',
            headers={'Content-disposition': 'attachment; filename=generated_consent.xml'}
        )

    except Exception as e:
        app.logger.exception('Consent generation failed')
        return 'Unable to generate the consent file. Please check the form and try again.', 500

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=int(os.environ.get('PORT', '5000')), debug=False)