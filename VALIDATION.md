# Local verification

Verified with Python 3.12 and the pinned application dependencies using Flask's test client.

- Homepage and health routes respond successfully.
- Consent generation produces a downloadable XML file.
- Optional audio, recontact and adverse-event sections toggle correctly.
- Country/contact assignment works for standard and custom countries.
- Duplicate country codes and invalid or missing inputs are rejected.
- XML special characters in project text are escaped.
- Generated XML structure is checked, tolerating Decipher namespace conventions.
- Company identifiers, original contact details and original access token are absent from the packaged source and sample generated output.
- External API/email actions are disabled in the demo template.

Not tested inside a live Decipher instance; placeholders must be configured and the entire survey reviewed before field use.

Cloud deployment and browser layout testing have not been performed.
