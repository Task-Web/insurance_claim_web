from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

from .models import StateMeta, UserState


class StateRequest(BaseModel):
    data: Dict[str, Any] = Field(default_factory=dict)
    note: Optional[str] = None
    meta: Optional[StateMeta] = None


class StatePatchRequest(BaseModel):
    data: Dict[str, Any] = Field(default_factory=dict)
    note: Optional[str] = None


class StateResponse(BaseModel):
    user_id: str
    state: UserState


class InfoResponse(BaseModel):
    app_name: str
    python_version: str
    env: Dict[str, str]
    request: Dict[str, Any]


class FileMetadata(BaseModel):
    id: str
    name: str
    size: int
    type: str
    url: str
    filename: str


class StrictRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ClaimFile(StrictRequest):
    id: str
    name: str
    originalName: str
    size: int = Field(ge=0)
    type: str
    url: Optional[str] = None
    filename: Optional[str] = None


class ClaimFormData(StrictRequest):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    insured_name: Optional[str] = Field(None, alias="insured-name")
    id_type: Optional[str] = Field(None, alias="id-type")
    id_number: Optional[str] = Field(None, alias="id-number")
    phone: Optional[str] = None
    accident_time: Optional[str] = Field(None, alias="accident-time")
    accident_situation: Optional[str] = Field(None, alias="accident-situation")
    incident: Optional[str] = None
    applicantType: Optional[str] = None
    patientType: Optional[str] = None
    payeeType: Optional[str] = None
    illness_hospital: Optional[str] = Field(None, alias="illness-hospital")
    illness_summary: Optional[str] = Field(None, alias="illness-summary")
    medication_fee: Optional[str] = Field(None, alias="medication-fee")
    examination_fee: Optional[str] = Field(None, alias="examination-fee")
    service_fee: Optional[str] = Field(None, alias="service-fee")
    outpatient_total: Optional[str] = Field(None, alias="outpatient-total")
    inpatient_total: Optional[str] = Field(None, alias="inpatient-total")
    common_hospital: Optional[str] = Field(None, alias="common-hospital")
    common_injury_area: Optional[str] = Field(None, alias="common-injury-area")
    common_severity: Optional[str] = Field(None, alias="common-severity")
    common_summary: Optional[str] = Field(None, alias="common-summary")
    common_medication_fee: Optional[str] = Field(None, alias="common-medication-fee")
    common_examination_fee: Optional[str] = Field(None, alias="common-examination-fee")
    common_service_fee: Optional[str] = Field(None, alias="common-service-fee")
    common_total: Optional[str] = Field(None, alias="common-total")
    traffic_location: Optional[str] = Field(None, alias="traffic-location")
    traffic_motor: Optional[str] = Field(None, alias="traffic-motor")
    traffic_police_report: Optional[str] = Field(None, alias="traffic-police-report")
    payee_name: Optional[str] = Field(None, alias="payee-name")
    payee_phone: Optional[str] = Field(None, alias="payee-phone")
    bank_card: Optional[str] = Field(None, alias="bank-card")
    account_relationship: Optional[str] = Field(None, alias="account-relationship")
    agreement: Optional[bool] = None
    claimSignature: Optional[str] = None


class ClaimDraft(StrictRequest):
    formData: ClaimFormData = Field(default_factory=ClaimFormData)
    uploadedFiles: List[ClaimFile] = Field(default_factory=list)
    currentStep: int = Field(ge=1, le=3)


class ClaimSubmission(StrictRequest):
    formData: ClaimFormData = Field(default_factory=ClaimFormData)
    uploadedFiles: List[ClaimFile] = Field(default_factory=list)


class ClaimWorkspaceResponse(BaseModel):
    user_id: str
    draft: Optional[Dict[str, Any]]
    submitted_claims: List[Dict[str, Any]]
