"""Report generator implementations for different output formats."""

import json
from pathlib import Path
from typing import Any, Dict

from .base import ReportGenerator
from .models import ReportData


class JSONReportGenerator(ReportGenerator):
    """Generate JSON format reports."""

    @property
    def file_extension(self) -> str:
        """File extension for JSON reports."""
        return "json"

    def generate(self, report_data: ReportData, filename: str) -> Path:
        """
        Generate a JSON report.

        Args:
            report_data: Complete report data
            filename: Base filename (without extension)

        Returns:
            Path to the generated JSON file
        """
        output_path = self.get_output_path(filename)

        # Convert to dictionary with proper serialization
        report_dict = self._serialize_report_data(report_data)

        # Write JSON file with pretty formatting
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(report_dict, f, indent=2, ensure_ascii=False, default=str)

        return output_path

    def _serialize_report_data(self, report_data: ReportData) -> Dict[str, Any]:
        """
        Convert ReportData to a JSON-serializable dictionary.

        Args:
            report_data: Report data to serialize

        Returns:
            JSON-serializable dictionary
        """
        # Convert the Pydantic models to dict with proper datetime handling
        data = report_data.model_dump(mode='json')

        # Add computed properties that aren't automatically serialized
        data["summary_stats"] = report_data.summary_stats
        data["failed_tests"] = [
            test.model_dump(mode='json') for test in report_data.failed_tests
        ]
        data["failed_measurements_by_test"] = {
            test_name: [m.model_dump(mode='json') for m in measurements]
            for test_name, measurements in report_data.failed_measurements_by_test.items()
        }

        return data


class HTMLReportGenerator(ReportGenerator):
    """Generate HTML format reports with embedded CSS and JavaScript."""

    @property
    def file_extension(self) -> str:
        """File extension for HTML reports."""
        return "html"

    def generate(self, report_data: ReportData, filename: str) -> Path:
        """
        Generate an HTML report.

        Args:
            report_data: Complete report data
            filename: Base filename (without extension)

        Returns:
            Path to the generated HTML file
        """
        output_path = self.get_output_path(filename)

        # Generate HTML content
        html_content = self._generate_html_content(report_data)

        # Write HTML file
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)

        return output_path

    def _generate_html_content(self, report_data: ReportData) -> str:
        """
        Generate the complete HTML content for the report.

        Args:
            report_data: Report data to render

        Returns:
            Complete HTML document as string
        """
        test_run = report_data.test_run
        stats = report_data.summary_stats

        # Generate test results table
        test_results_html = self._generate_test_results_table(test_run.test_results)

        # Generate failed tests section if any
        failed_tests_html = ""
        if report_data.failed_tests:
            failed_tests_html = self._generate_failed_tests_section(report_data.failed_tests)

        # Generate measurements summary
        measurements_html = self._generate_measurements_summary(report_data)

        html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Test Report - {test_run.run_id}</title>
    <style>
        {self._get_css_styles()}
    </style>
</head>
<body>
    <div class="container">
        <header class="report-header">
            <h1>Electronics HAL Test Report</h1>
            <div class="run-info">
                <span class="run-id">Run ID: {test_run.run_id}</span>
                <span class="status status-{test_run.status.lower()}">{test_run.status}</span>
            </div>
            <div class="generation-info">
                <span>Generated: {report_data.generation_time.strftime('%Y-%m-%d %H:%M:%S')}</span>
                <span>Report Version: {report_data.report_version}</span>
            </div>
        </header>

        <section class="summary">
            <h2>Test Summary</h2>
            <div class="summary-grid">
                <div class="summary-card">
                    <h3>Test Execution</h3>
                    <div class="metric">
                        <span class="value">{stats['total_tests']}</span>
                        <span class="label">Total Tests</span>
                    </div>
                    <div class="metric-row">
                        <div class="metric passed">
                            <span class="value">{stats['passed_tests']}</span>
                            <span class="label">Passed</span>
                        </div>
                        <div class="metric failed">
                            <span class="value">{stats['failed_tests']}</span>
                            <span class="label">Failed</span>
                        </div>
                        <div class="metric skipped">
                            <span class="value">{stats['skipped_tests']}</span>
                            <span class="label">Skipped</span>
                        </div>
                    </div>
                    <div class="success-rate">
                        <span class="rate">{stats['success_rate']:.1f}%</span>
                        <span class="label">Success Rate</span>
                    </div>
                </div>

                <div class="summary-card">
                    <h3>Measurements</h3>
                    <div class="metric">
                        <span class="value">{stats['total_measurements']}</span>
                        <span class="label">Total Measurements</span>
                    </div>
                    <div class="metric-row">
                        <div class="metric passed">
                            <span class="value">{stats['passed_measurements']}</span>
                            <span class="label">Passed</span>
                        </div>
                        <div class="metric failed">
                            <span class="value">{stats['failed_measurements']}</span>
                            <span class="label">Failed</span>
                        </div>
                    </div>
                    <div class="success-rate">
                        <span class="rate">{stats['measurement_success_rate']:.1f}%</span>
                        <span class="label">Success Rate</span>
                    </div>
                </div>

                <div class="summary-card">
                    <h3>Execution Time</h3>
                    <div class="metric">
                        <span class="value">{self._format_duration(stats.get('duration'))}</span>
                        <span class="label">Total Duration</span>
                    </div>
                    <div class="time-info">
                        <div>Started: {test_run.start_time.strftime('%Y-%m-%d %H:%M:%S')}</div>
                        {f'<div>Finished: {test_run.end_time.strftime("%Y-%m-%d %H:%M:%S")}</div>' if test_run.end_time else '<div>Status: In Progress</div>'}
                    </div>
                </div>
            </div>
        </section>

        <section class="test-results">
            <h2>Test Results</h2>
            {test_results_html}
        </section>

        {failed_tests_html}

        {measurements_html}

        <section class="configuration">
            <h2>Test Configuration</h2>
            <pre class="config-json">{json.dumps(test_run.configuration_snapshot, indent=2)}</pre>
        </section>
    </div>

    <script>
        {self._get_javascript()}
    </script>
</body>
</html>"""
        return html_content

    def _generate_test_results_table(self, test_results) -> str:
        """Generate HTML table for test results."""
        if not test_results:
            return "<p>No test results found.</p>"

        rows = []
        for test in test_results:
            outcome_class = test.outcome.lower()
            measurements_info = f"{test.passed_measurements}/{test.total_measurements}" if test.total_measurements > 0 else "0/0"

            rows.append(f"""
                <tr class="test-row {outcome_class}">
                    <td class="test-name">{test.test_name}</td>
                    <td class="outcome">
                        <span class="status status-{outcome_class}">{test.outcome}</span>
                    </td>
                    <td class="duration">{test.duration:.3f}s</td>
                    <td class="measurements">{measurements_info}</td>
                    <td class="error">
                        {test.error_message[:100] + '...' if test.error_message and len(test.error_message) > 100 else test.error_message or ''}
                    </td>
                </tr>
            """)

        return f"""
            <table class="test-table">
                <thead>
                    <tr>
                        <th>Test Name</th>
                        <th>Outcome</th>
                        <th>Duration</th>
                        <th>Measurements</th>
                        <th>Error</th>
                    </tr>
                </thead>
                <tbody>
                    {''.join(rows)}
                </tbody>
            </table>
        """

    def _generate_failed_tests_section(self, failed_tests) -> str:
        """Generate detailed section for failed tests."""
        failed_details = []
        for test in failed_tests:
            failed_measurements = [m for m in test.measurements if not m.passed]
            measurements_html = ""

            if failed_measurements:
                measurement_rows = []
                for m in failed_measurements:
                    limits_str = ""
                    if m.limits:
                        limits_str = f"Limits: {m.limits}"

                    measurement_rows.append(f"""
                        <tr>
                            <td>{m.name}</td>
                            <td>{m.value} {m.unit}</td>
                            <td>{limits_str}</td>
                        </tr>
                    """)

                measurements_html = f"""
                    <h4>Failed Measurements</h4>
                    <table class="measurements-table">
                        <thead>
                            <tr>
                                <th>Measurement</th>
                                <th>Value</th>
                                <th>Limits</th>
                            </tr>
                        </thead>
                        <tbody>
                            {''.join(measurement_rows)}
                        </tbody>
                    </table>
                """

            failed_details.append(f"""
                <div class="failed-test">
                    <h3>{test.test_name}</h3>
                    <div class="test-details">
                        <p><strong>Error:</strong> {test.error_message or 'No error message'}</p>
                        <p><strong>Duration:</strong> {test.duration:.3f}s</p>
                        <p><strong>Started:</strong> {test.start_time.strftime('%Y-%m-%d %H:%M:%S')}</p>
                    </div>
                    {measurements_html}
                </div>
            """)

        return f"""
            <section class="failed-tests">
                <h2>Failed Tests Details</h2>
                {''.join(failed_details)}
            </section>
        """

    def _generate_measurements_summary(self, report_data: ReportData) -> str:
        """Generate measurements summary section."""
        failed_by_test = report_data.failed_measurements_by_test

        if not failed_by_test:
            return ""

        test_sections = []
        for test_name, measurements in failed_by_test.items():
            measurement_rows = []
            for m in measurements:
                limits_str = ""
                if m.limits:
                    limits_str = f"Min: {m.limits.get('min', 'N/A')}, Max: {m.limits.get('max', 'N/A')}"

                measurement_rows.append(f"""
                    <tr>
                        <td>{m.name}</td>
                        <td>{m.value}</td>
                        <td>{m.unit}</td>
                        <td>{limits_str}</td>
                        <td>{m.timestamp.strftime('%H:%M:%S')}</td>
                    </tr>
                """)

            test_sections.append(f"""
                <div class="test-measurements">
                    <h3>{test_name}</h3>
                    <table class="measurements-table">
                        <thead>
                            <tr>
                                <th>Measurement</th>
                                <th>Value</th>
                                <th>Unit</th>
                                <th>Limits</th>
                                <th>Time</th>
                            </tr>
                        </thead>
                        <tbody>
                            {''.join(measurement_rows)}
                        </tbody>
                    </table>
                </div>
            """)

        return f"""
            <section class="failed-measurements">
                <h2>Failed Measurements Details</h2>
                {''.join(test_sections)}
            </section>
        """

    def _format_duration(self, duration) -> str:
        """Format duration in a human-readable way."""
        if duration is None:
            return "N/A"

        if duration < 60:
            return f"{duration:.1f}s"
        elif duration < 3600:
            minutes = duration // 60
            seconds = duration % 60
            return f"{int(minutes)}m {seconds:.1f}s"
        else:
            hours = duration // 3600
            minutes = (duration % 3600) // 60
            seconds = duration % 60
            return f"{int(hours)}h {int(minutes)}m {seconds:.1f}s"

    def _get_css_styles(self) -> str:
        """Get CSS styles for the HTML report."""
        return """
        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            line-height: 1.6;
            color: #333;
            background-color: #f5f5f5;
        }

        .container {
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background-color: white;
            box-shadow: 0 0 10px rgba(0,0,0,0.1);
        }

        .report-header {
            border-bottom: 2px solid #e0e0e0;
            padding-bottom: 20px;
            margin-bottom: 30px;
        }

        .report-header h1 {
            color: #2c3e50;
            margin-bottom: 10px;
        }

        .run-info {
            display: flex;
            align-items: center;
            gap: 15px;
            margin-bottom: 10px;
        }

        .run-id {
            font-family: monospace;
            background-color: #f8f9fa;
            padding: 4px 8px;
            border-radius: 4px;
            border: 1px solid #e9ecef;
        }

        .status {
            padding: 4px 12px;
            border-radius: 20px;
            font-weight: bold;
            text-transform: uppercase;
            font-size: 0.8em;
        }

        .status-completed { background-color: #d4edda; color: #155724; }
        .status-failed { background-color: #f8d7da; color: #721c24; }
        .status-in_progress { background-color: #fff3cd; color: #856404; }

        .generation-info {
            font-size: 0.9em;
            color: #666;
        }

        .generation-info span {
            margin-right: 20px;
        }

        section {
            margin-bottom: 40px;
        }

        h2 {
            color: #2c3e50;
            border-bottom: 1px solid #e0e0e0;
            padding-bottom: 10px;
            margin-bottom: 20px;
        }

        .summary-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin-bottom: 20px;
        }

        .summary-card {
            background-color: #f8f9fa;
            border: 1px solid #e9ecef;
            border-radius: 8px;
            padding: 20px;
        }

        .summary-card h3 {
            color: #495057;
            margin-bottom: 15px;
            font-size: 1.1em;
        }

        .metric {
            text-align: center;
            margin-bottom: 15px;
        }

        .metric .value {
            display: block;
            font-size: 2em;
            font-weight: bold;
            color: #2c3e50;
        }

        .metric .label {
            display: block;
            font-size: 0.9em;
            color: #666;
            text-transform: uppercase;
        }

        .metric-row {
            display: flex;
            justify-content: space-around;
            margin-bottom: 15px;
        }

        .metric-row .metric {
            margin-bottom: 0;
        }

        .metric-row .metric .value {
            font-size: 1.5em;
        }

        .metric.passed .value { color: #28a745; }
        .metric.failed .value { color: #dc3545; }
        .metric.skipped .value { color: #ffc107; }

        .success-rate {
            text-align: center;
            padding-top: 15px;
            border-top: 1px solid #dee2e6;
        }

        .success-rate .rate {
            display: block;
            font-size: 1.8em;
            font-weight: bold;
            color: #17a2b8;
        }

        .time-info {
            font-size: 0.9em;
            color: #666;
            margin-top: 10px;
        }

        .test-table, .measurements-table {
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 20px;
        }

        .test-table th, .test-table td,
        .measurements-table th, .measurements-table td {
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #e0e0e0;
        }

        .test-table th, .measurements-table th {
            background-color: #f8f9fa;
            font-weight: bold;
            color: #495057;
        }

        .test-row.failed {
            background-color: #fff5f5;
        }

        .test-row.passed {
            background-color: #f0fff4;
        }

        .test-row.skipped {
            background-color: #fffbf0;
        }

        .test-name {
            font-family: monospace;
            font-weight: bold;
        }

        .outcome .status {
            font-size: 0.8em;
        }

        .status-passed { background-color: #d4edda; color: #155724; }
        .status-failed { background-color: #f8d7da; color: #721c24; }
        .status-skipped { background-color: #fff3cd; color: #856404; }

        .duration {
            font-family: monospace;
        }

        .error {
            font-size: 0.9em;
            color: #666;
            max-width: 300px;
            word-wrap: break-word;
        }

        .failed-test {
            background-color: #fff5f5;
            border: 1px solid #f5c6cb;
            border-radius: 8px;
            padding: 20px;
            margin-bottom: 20px;
        }

        .failed-test h3 {
            color: #721c24;
            margin-bottom: 10px;
        }

        .test-details {
            margin-bottom: 15px;
        }

        .test-details p {
            margin-bottom: 5px;
        }

        .config-json {
            background-color: #f8f9fa;
            border: 1px solid #e9ecef;
            border-radius: 4px;
            padding: 15px;
            overflow-x: auto;
            font-family: monospace;
            font-size: 0.9em;
        }

        @media (max-width: 768px) {
            .container {
                padding: 10px;
            }

            .summary-grid {
                grid-template-columns: 1fr;
            }

            .metric-row {
                flex-direction: column;
                gap: 10px;
            }

            .test-table, .measurements-table {
                font-size: 0.9em;
            }
        }
        """

    def _get_javascript(self) -> str:
        """Get JavaScript for interactive features."""
        return """
        // Add click handlers for expandable sections
        document.addEventListener('DOMContentLoaded', function() {
            // Add sorting to tables
            const tables = document.querySelectorAll('.test-table');
            tables.forEach(table => {
                const headers = table.querySelectorAll('th');
                headers.forEach((header, index) => {
                    header.style.cursor = 'pointer';
                    header.addEventListener('click', () => sortTable(table, index));
                });
            });
        });

        function sortTable(table, column) {
            const tbody = table.tBodies[0];
            const rows = Array.from(tbody.rows);
            const isNumeric = column === 2; // Duration column

            rows.sort((a, b) => {
                const aVal = a.cells[column].textContent.trim();
                const bVal = b.cells[column].textContent.trim();

                if (isNumeric) {
                    return parseFloat(aVal) - parseFloat(bVal);
                }

                return aVal.localeCompare(bVal);
            });

            rows.forEach(row => tbody.appendChild(row));
        }
        """


class PDFReportGenerator(ReportGenerator):
    """Generate PDF format reports."""

    @property
    def file_extension(self) -> str:
        """File extension for PDF reports."""
        return "pdf"

    def generate(self, report_data: ReportData, filename: str) -> Path:
        """
        Generate a PDF report.

        Args:
            report_data: Complete report data
            filename: Base filename (without extension)

        Returns:
            Path to the generated PDF file
        """
        try:
            from reportlab.lib import colors
            from reportlab.lib.pagesizes import A4, letter
            from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
            from reportlab.lib.units import inch
            from reportlab.platypus import (
                PageBreak,
                Paragraph,
                SimpleDocTemplate,
                Spacer,
                Table,
                TableStyle,
            )
        except ImportError:
            raise ImportError(
                "reportlab is required for PDF generation. Install with: pip install reportlab"
            )

        output_path = self.get_output_path(filename)

        # Create the PDF document
        doc = SimpleDocTemplate(str(output_path), pagesize=A4)
        styles = getSampleStyleSheet()
        story = []

        # Add custom styles
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            spaceAfter=30,
            textColor=colors.darkblue
        )

        heading_style = ParagraphStyle(
            'CustomHeading',
            parent=styles['Heading2'],
            fontSize=16,
            spaceAfter=12,
            textColor=colors.darkblue
        )

        # Title and header
        story.append(Paragraph("Electronics HAL Test Report", title_style))
        story.append(Paragraph(f"Run ID: {report_data.test_run.run_id}", styles['Normal']))
        story.append(Paragraph(f"Status: {report_data.test_run.status}", styles['Normal']))
        story.append(Paragraph(f"Generated: {report_data.generation_time.strftime('%Y-%m-%d %H:%M:%S')}", styles['Normal']))
        story.append(Spacer(1, 20))

        # Summary statistics
        story.append(Paragraph("Test Summary", heading_style))
        stats = report_data.summary_stats

        summary_data = [
            ['Metric', 'Value'],
            ['Total Tests', str(stats['total_tests'])],
            ['Passed Tests', str(stats['passed_tests'])],
            ['Failed Tests', str(stats['failed_tests'])],
            ['Skipped Tests', str(stats['skipped_tests'])],
            ['Success Rate', f"{stats['success_rate']:.1f}%"],
            ['Total Measurements', str(stats['total_measurements'])],
            ['Passed Measurements', str(stats['passed_measurements'])],
            ['Failed Measurements', str(stats['failed_measurements'])],
            ['Measurement Success Rate', f"{stats['measurement_success_rate']:.1f}%"],
            ['Duration', self._format_duration(stats.get('duration'))],
        ]

        summary_table = Table(summary_data, colWidths=[3*inch, 2*inch])
        summary_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        story.append(summary_table)
        story.append(Spacer(1, 20))

        # Test results table
        story.append(Paragraph("Test Results", heading_style))
        if report_data.test_run.test_results:
            test_data = [['Test Name', 'Outcome', 'Duration', 'Measurements']]

            for test in report_data.test_run.test_results:
                measurements_info = f"{test.passed_measurements}/{test.total_measurements}" if test.total_measurements > 0 else "0/0"
                test_data.append([
                    test.test_name,
                    test.outcome,
                    f"{test.duration:.3f}s",
                    measurements_info
                ])

            test_table = Table(test_data, colWidths=[3*inch, 1*inch, 1*inch, 1*inch])
            test_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('FONTSIZE', (0, 1), (-1, -1), 8),
            ]))
            story.append(test_table)
        else:
            story.append(Paragraph("No test results found.", styles['Normal']))

        story.append(Spacer(1, 20))

        # Failed tests details
        if report_data.failed_tests:
            story.append(Paragraph("Failed Tests Details", heading_style))
            for test in report_data.failed_tests:
                story.append(Paragraph(f"<b>{test.test_name}</b>", styles['Normal']))
                story.append(Paragraph(f"Error: {test.error_message or 'No error message'}", styles['Normal']))
                story.append(Paragraph(f"Duration: {test.duration:.3f}s", styles['Normal']))

                failed_measurements = [m for m in test.measurements if not m.passed]
                if failed_measurements:
                    story.append(Paragraph("Failed Measurements:", styles['Normal']))
                    meas_data = [['Measurement', 'Value', 'Unit', 'Limits']]
                    for m in failed_measurements:
                        limits_str = ""
                        if m.limits:
                            limits_str = f"Min: {m.limits.get('min', 'N/A')}, Max: {m.limits.get('max', 'N/A')}"
                        meas_data.append([m.name, str(m.value), m.unit, limits_str])

                    meas_table = Table(meas_data, colWidths=[2*inch, 1*inch, 1*inch, 2*inch])
                    meas_table.setStyle(TableStyle([
                        ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
                        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                        ('FONTSIZE', (0, 0), (-1, -1), 8),
                        ('GRID', (0, 0), (-1, -1), 1, colors.black)
                    ]))
                    story.append(meas_table)

                story.append(Spacer(1, 12))

        # Build the PDF
        doc.build(story)
        return output_path

    def _format_duration(self, duration) -> str:
        """Format duration in a human-readable way."""
        if duration is None:
            return "N/A"

        if duration < 60:
            return f"{duration:.1f}s"
        elif duration < 3600:
            minutes = duration // 60
            seconds = duration % 60
            return f"{int(minutes)}m {seconds:.1f}s"
        else:
            hours = duration // 3600
            minutes = (duration % 3600) // 60
            seconds = duration % 60
            return f"{int(hours)}h {int(minutes)}m {seconds:.1f}s"
