
from pathlib import Path as FilePath
from uuid import uuid4

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Path as APIPath,
    UploadFile,
    status,
)
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.dependencies import (
    get_current_user,
    get_tenant_scope,
    require_roles,
)
from app.enums import RoleEnum
from app.db.models.user import User

from app.crud.expense_crud import get_expense
from app.crud.expense_document_crud import (
    create_expense_document,
    get_expense_documents,
    get_expense_document,
    delete_expense_document,
)
from app.schemas.expense_document_schema import ExpenseDocumentResponse


router = APIRouter(
    prefix="/expenses/{expense_id}/documents",
    tags=["Expense Documents"],
)

UPLOAD_DIR = FilePath("uploads/expense_documents")

ALLOWED_EXTENSIONS = {
    ".pdf",
    ".png",
    ".jpg",
    ".jpeg",
    ".doc",
    ".docx",
    ".xlsx",
}

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
CHUNK_SIZE = 1024 * 1024  # 1 MB


def get_company_id(scope: dict) -> int:
    company_id = scope.get("company_id")

    if company_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Company scope is missing.",
        )

    return int(company_id)


# UPLOAD DOCUMENT FOR PENDING EXPENSE
@router.post(
    "/",
    response_model=ExpenseDocumentResponse,
    status_code=status.HTTP_201_CREATED,
)
def upload_expense_document(
    expense_id: int = APIPath(..., ge=1),
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    scope: dict = Depends(get_tenant_scope),
    db: Session = Depends(get_db),
):
    company_id = get_company_id(scope)

    original_filename = FilePath(file.filename or "").name

    if not original_filename or original_filename in {".", ".."}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A valid filename is required.",
        )

    extension = FilePath(original_filename).suffix.lower()

    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported file type.",
        )

    expense = get_expense(
        db=db,
        expense_id=expense_id,
        company_id=company_id,
    )

    if expense is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Expense not found.",
        )

    if expense.status != "Pending":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Documents can only be uploaded for Pending expenses.",
        )

    upload_dir = UPLOAD_DIR / str(company_id) / str(expense_id)
    file_path = None
    total_size = 0

    try:
        upload_dir.mkdir(parents=True, exist_ok=True)

        stored_filename = f"{uuid4().hex}{extension}"
        file_path = upload_dir / stored_filename

        with file_path.open("wb") as destination:
            while True:
                chunk = file.file.read(CHUNK_SIZE)

                if not chunk:
                    break

                total_size += len(chunk)

                if total_size > MAX_FILE_SIZE:
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail="File size must not exceed 10 MB.",
                    )

                destination.write(chunk)

        if total_size == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded file is empty.",
            )

        document = create_expense_document(
            db=db,
            expense_id=expense_id,
            company_id=company_id,
            document_name=original_filename,
            document_path=str(file_path),
            document_type=file.content_type,
            uploaded_by=current_user.user_id,
        )

        if document is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "Document could not be saved. "
                    "Ensure the expense is still Pending."
                ),
            )

        return document

    except HTTPException:
        if file_path is not None:
            try:
                file_path.unlink(missing_ok=True)
            except OSError:
                pass
        raise

    except Exception:
        if file_path is not None:
            try:
                file_path.unlink(missing_ok=True)
            except OSError:
                pass

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not save expense document.",
        )

    finally:
        file.file.close()


# LIST DOCUMENTS FOR AN EXPENSE
@router.get(
    "/",
    response_model=list[ExpenseDocumentResponse],
)
def list_expense_documents(
    expense_id: int = APIPath(..., ge=1),
    current_user: User = Depends(
        require_roles(RoleEnum.ADMIN)
    ),
    scope: dict = Depends(get_tenant_scope),
    db: Session = Depends(get_db),
):
    documents = get_expense_documents(
        db=db,
        expense_id=expense_id,
        company_id=get_company_id(scope),
    )

    if documents is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Expense not found.",
        )

    return documents



# DELETE DOCUMENT FROM PENDING EXPENSE
@router.delete(
    "/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def remove_expense_document(
    expense_id: int = APIPath(..., ge=1),
    document_id: int = APIPath(..., ge=1),
    current_user: User = Depends(get_current_user),
    scope: dict = Depends(get_tenant_scope),
    db: Session = Depends(get_db),
):
    company_id = get_company_id(scope)

    expense = get_expense(
        db=db,
        expense_id=expense_id,
        company_id=company_id,
    )

    if expense is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Expense not found.",
        )

    # Documents can only be deleted while expense is Pending
    if expense.status != "Pending":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Documents can only be deleted from Pending expenses.",
        )

    document = get_expense_document(
        db=db,
        document_id=document_id,
        expense_id=expense_id,
        company_id=company_id,
    )

    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Expense document not found.",
        )

    # Only the user who uploaded the document can delete it
    if document.uploaded_by != current_user.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the user who uploaded the document is authorized to delete it.",
        )

    file_path = FilePath(document.document_path)

    delete_expense_document(
        db=db,
        document=document,
    )

    try:
        file_path.unlink(missing_ok=True)
    except OSError:
        pass

    return None
