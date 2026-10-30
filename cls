warning: in the working copy of 'backend/app/services/cover_service.py', LF will be replaced by CRLF the next time Git touches it
[1mdiff --git a/backend/app/services/cover_service.py b/backend/app/services/cover_service.py[m
[1mindex 0cfbfa5..1293b02 100644[m
[1m--- a/backend/app/services/cover_service.py[m
[1m+++ b/backend/app/services/cover_service.py[m
[36m@@ -143,37 +143,41 @@[m [mdef list_invites_for(db: Session, instructor_id: uuid.UUID) -> list[CoverInvite][m
     )[m
 [m
 [m
 def accept_invite([m
     db: Session, instructor: User, invite_id: uuid.UUID[m
 ) -> tuple[str, CoverInvite]:[m
     """Primeiro aceite vence — dentro de UMA transação.[m
 [m
     Retorna (outcome, invite): outcome ∈ {accepted, already_taken, expired}.[m
     """[m
[31m-    # Lock pessimista do convite para garantir o primeiro aceite.[m
[31m-    # of=CoverInvite evita bloquear relacionamentos joined nullable.[m
[32m+[m[32m    invite = db.scalar(select(CoverInvite).where(CoverInvite.id == invite_id))[m
[32m+[m[32m    if invite is None or invite.invited_instructor_id != instructor.id:[m
[32m+[m[32m        raise CoverError("not_found", "Convite não encontrado.")[m
[32m+[m
[32m+[m[32m    # Todos os caminhos de decisão bloqueiam primeiro a solicitação e depois[m
[32m+[m[32m    # o convite, evitando que a atualização dos demais convites forme ciclo.[m
[32m+[m[32m    request = _lock_request(db, invite.request_id)[m
[32m+[m[32m    if request is None:[m
[32m+[m[32m        raise CoverError("request_closed", "Solicitação não está mais aberta.")[m
[32m+[m
     stmt = select(CoverInvite).where(CoverInvite.id == invite_id).with_for_update(of=CoverInvite)[m
     invite = db.execute(stmt).scalar_one_or_none()[m
     if invite is None or invite.invited_instructor_id != instructor.id:[m
         raise CoverError("not_found", "Convite não encontrado.")[m
[31m-[m
     if invite.status == CoverInviteStatus.TAKEN:[m
         return "already_taken", invite[m
     if invite.status == CoverInviteStatus.EXPIRED:[m
         return "expired", invite[m
     if invite.status != CoverInviteStatus.PENDING:[m
         raise CoverError("not_pending", "Convite não está mais aberto.")[m
[31m-[m
[31m-    request = _lock_request(db, invite.request_id)[m
[31m-    if request is None or request.status != CoverRequestStatus.OPEN:[m
[31m-        # Solicitação resolvida depois que o convite foi emitido.[m
[32m+[m[32m    if request.status != CoverRequestStatus.OPEN:[m
         invite.status = CoverInviteStatus.TAKEN[m
         invite.resolved_at = datetime.now(UTC)[m
         return "already_taken", invite[m
 [m
     session_row = _lock_session(db, request.session_id)[m
     if session_row is None:[m
         raise CoverError("session_not_found", "Sessão não encontrada.")[m
 [m
     now = datetime.now(UTC)[m
     # Vencedor: assume a sessão.[m
[36m@@ -204,31 +208,37 @@[m [mdef accept_invite([m
 [m
 [m
 def decline_invite([m
     db: Session, instructor: User, invite_id: uuid.UUID[m
 ) -> tuple[CoverInvite, CoverRequest]:[m
     """Recusa; quando todos recusarem, resolve como uncovered.[m
 [m
     Operação transacional: bloqueia a solicitação para evitar corrida com[m
     um aceite simultâneo.[m
     """[m
[31m-    # Lock pessimista do convite para evitar corrida com aceite simultâneo.[m
[31m-    # of=CoverInvite evita bloquear relacionamentos joined nullable.[m
[32m+[m[32m    invite = db.scalar(select(CoverInvite).where(CoverInvite.id == invite_id))[m
[32m+[m[32m    if invite is None or invite.invited_instructor_id != instructor.id:[m
[32m+[m[32m        raise CoverError("not_found", "Convite não encontrado.")[m
[32m+[m
[32m+[m[32m    # A solicitação é sempre bloqueada antes do convite, como em[m
[32m+[m[32m    # accept_invite(), para evitar deadlocks entre decisões concorrentes.[m
[32m+[m[32m    request = _lock_request(db, invite.request_id)[m
[32m+[m[32m    if request is None:[m
[32m+[m[32m        raise CoverError("request_closed", "Solicitação não está mais aberta.")[m
[32m+[m
     stmt = select(CoverInvite).where(CoverInvite.id == invite_id).with_for_update(of=CoverInvite)[m
     invite = db.execute(stmt).scalar_one_or_none()[m
     if invite is None or invite.invited_instructor_id != instructor.id:[m
         raise CoverError("not_found", "Convite não encontrado.")[m
     if invite.status != CoverInviteStatus.PENDING:[m
         raise CoverError("not_pending", "Convite não está mais aberto.")[m
[31m-[m
[31m-    request = _lock_request(db, invite.request_id)[m
[31m-    if request is None or request.status != CoverRequestStatus.OPEN:[m
[32m+[m[32m    if request.status != CoverRequestStatus.OPEN:[m
         raise CoverError("request_closed", "Solicitação não está mais aberta.")[m
 [m
     invite.status = CoverInviteStatus.DECLINED[m
     invite.declined_at = datetime.now(UTC)[m
     invite.resolved_at = invite.declined_at[m
 [m
     remaining = db.scalar([m
         select(CoverInvite.id)[m
         .where([m
             CoverInvite.request_id == request.id,[m
