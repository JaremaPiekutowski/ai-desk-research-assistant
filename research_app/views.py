from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponse, FileResponse, HttpResponseBadRequest, HttpResponseServerError
from django.conf import settings
from django.urls import reverse
from django.views.decorators.http import require_POST, require_GET
from django.views.decorators.csrf import csrf_exempt # Use carefully, consider alternatives if needed
import json
import os
import time # For simulating delays if not using Celery

from .models import ResearchSession, UploadedDocument
from .forms import ResearchForm
from .utils import (
    add_answer_to_report,
    add_summary_to_report,
    extract_text,
    initialize_report,
    query_gemini_single_doc,
    query_gemini_summary,
    save_report,
)


def index(request):
    """Displays the main upload form."""
    form = ResearchForm()
    return render(request, 'research_app/index.html', {'form': form})

@require_POST # Only allow POST requests
def start_research_session(request):
    """Handles form submission, creates session, saves files, and starts processing."""
    form = ResearchForm(request.POST, request.FILES)

    if form.is_valid():
        query = form.cleaned_data['query']
        uploaded_files = form.cleaned_data['documents'] # Already validated list of files

        # 1. Create Research Session
        session = ResearchSession.objects.create(query=query)

        # 2. Create UploadedDocument entries
        for uploaded_file in uploaded_files:
            # Sanitize filename (optional but good practice)
            original_filename = uploaded_file.name
            doc = UploadedDocument.objects.create(
                session=session,
                file=uploaded_file,
                original_filename=original_filename,
                status='uploaded'
            )
            print(f"Saved document record: {doc.id} for session {session.session_id}")


        # 3. Trigger background processing (Simulated Synchronously Here)
        # ****** PRODUCTION NOTE ******
        # In production, replace the direct call below with:
        # process_research_task.delay(session.session_id)
        # You'd need to define this Celery task in tasks.py
        # ****************************
        print(f"Starting synchronous processing for session {session.session_id}...")
        process_research_sync(session.session_id) # Call the synchronous version directly

        # Respond with HTMX to start polling for status
        # Render the initial state of the progress area
        context = {'session': session, 'documents': session.documents.all()}
        return render(request, 'research_app/_progress_area.html', context)

    else:
        # Form is invalid, re-render the index page with errors
        # This part might need refinement for HTMX - perhaps return an error partial
         print("Form errors:", form.errors)
         # For simplicity, just redirecting back for now. A better HTMX way
         # would be to return the form with errors in an HX-Swap.
         # return render(request, 'research_app/index.html', {'form': form}) # This would cause full page reload
         # Return a simple error message targetable by HTMX
         return HttpResponseBadRequest("Form validation failed. Please check your input and file types.")


# --- Synchronous Processing Function (Replace with Celery Task) ---
def process_research_sync(session_id):
    """
    Synchronous version of the processing logic.
    *** DO NOT USE IN PRODUCTION *** Use Celery instead.
    """
    try:
        session = ResearchSession.objects.get(pk=session_id)
        session.status = 'processing'
        session.save()

        # Initialize report
        report_doc = initialize_report(session.query)
        all_individual_answers = []
        all_answers_text_for_summary = ""

        documents = session.documents.all()

        # 5. Loop over documents
        for doc in documents:
            print(f"Processing document: {doc.original_filename}")
            # Update status for UI feedback
            doc.status = 'converting'; doc.save()
            time.sleep(0.1) # Simulate work / allow UI update if polling fast

            # Extract text
            text, metadata = extract_text(doc) # This updates doc status internally
            metadata_string = json.dumps(metadata)
            extracted_text = f"Metadata: {metadata_string}\n\nText: {text}"

            if doc.status == 'converted':
                doc.status = 'processing'; doc.save()
                time.sleep(0.1)

                # Make Gemini call
                print(f"Querying LLM for: {doc.original_filename}")
                answer, quotes = query_gemini_single_doc(
                    extracted_text,
                    session.query,
                    doc.original_filename
                )

                # Save answer to report and list
                add_answer_to_report(report_doc, doc.original_filename, answer)
                answer_with_source = f"--- Document: {doc.original_filename} ---\n{answer}\n\n"
                all_individual_answers.append({
                    'filename': doc.original_filename,
                    'answer': answer,
                    'quotes': quotes,
                })
                all_answers_text_for_summary += answer_with_source

                if "Error:" in answer:
                     doc.status = 'error'
                     doc.processing_log = answer
                else:
                     doc.status = 'processed'
                doc.save()
            elif doc.status == 'error':
                # Add error note to report
                add_answer_to_report(report_doc, doc.original_filename, f"Error processing document: {doc.processing_log or 'Extraction failed'}")
            else: # Should not happen if extract_text works correctly
                doc.status = 'error'
                doc.processing_log = "Unknown processing error after conversion attempt."
                doc.save()
                add_answer_to_report(report_doc, doc.original_filename, "Error: Unknown processing state.")


        # Create summary
        print(f"Generating summary for session {session.session_id}")
        session.status = 'summarizing'; session.save()
        time.sleep(0.1)

        summary_answer = query_gemini_summary(all_answers_text_for_summary, session.query)
        add_summary_to_report(report_doc, summary_answer)

        # Save the final report
        saved_path = save_report(report_doc, session) # Updates session filename

        if saved_path and "Error:" not in summary_answer:
             session.status = 'completed'
             session.error_message = None
             print(f"Session {session.session_id} completed successfully.")
        elif "Error:" in summary_answer:
            session.status = 'failed'
            session.error_message = f"Failed during summary generation: {summary_answer}"
            print(f"Session {session.session_id} failed during summary.")
        else: # Error during saving is handled in save_report
             session.status = 'failed' # Already set if save_report failed
             print(f"Session {session.session_id} failed during report saving.")

        session.save()

    except ResearchSession.DoesNotExist:
         print(f"Error: Session {session_id} not found during processing.")
    except Exception as e:
        print(f"Unhandled error during processing session {session_id}: {e}")
        try:
            # Try to mark the session as failed
            session = ResearchSession.objects.get(pk=session_id)
            session.status = 'failed'
            session.error_message = f"Unexpected processing error: {e}"
            session.save()
        except ResearchSession.DoesNotExist:
             pass # Session doesn't exist anyway
        except Exception as inner_e:
             print(f"Further error trying to mark session {session_id} as failed: {inner_e}")

# --- Status and Download Views ---

@require_GET
def get_session_status(request, session_id):
    """Returns the current status of the session and documents for HTMX polling."""
    try:
        session = ResearchSession.objects.get(pk=session_id)
        documents = session.documents.all().order_by('original_filename')
        context = {'session': session, 'documents': documents}

        # Decide which partial to render based on status
        if session.status == 'completed':
             # Render the results area containing the download link
             return render(request, 'research_app/_results_area.html', context)
        elif session.status == 'failed':
             # Render the progress area, which will show the failure status
             return render(request, 'research_app/_progress_area.html', context)
        else:
             # Render the progress area, which includes the polling trigger
             return render(request, 'research_app/_progress_area.html', context)

    except ResearchSession.DoesNotExist:
        # Render an error message or an empty div if session not found
         return HttpResponse("Session not found.", status=404)
    except Exception as e:
         print(f"Error fetching status for {session_id}: {e}")
         # Return a generic server error response
         return HttpResponseServerError("An error occurred while fetching status.")


@require_GET
def download_report(request, session_id):
    """Serves the generated DOCX report file for download."""
    session = get_object_or_404(ResearchSession, pk=session_id, status='completed')

    if not session.report_filename:
        return HttpResponse("Report file not found for this session.", status=404)

    report_path = session.get_report_path()

    if report_path and os.path.exists(report_path):
        try:
            # Use FileResponse for efficient file serving
            return FileResponse(open(report_path, 'rb'), as_attachment=True, filename=session.report_filename)
        except Exception as e:
             print(f"Error serving file {report_path}: {e}")
             return HttpResponseServerError("Error serving the report file.")
    else:
        return HttpResponse("Report file not found or is inaccessible.", status=404)
