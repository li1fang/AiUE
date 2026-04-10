#include "PMXEquipmentBlueprintLibrary.h"

#include "Animation/AnimationAsset.h"
#include "Components/SceneComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "GameFramework/Actor.h"
#include "NiagaraComponent.h"
#include "NiagaraSystem.h"
#include "NiagaraWorldManager.h"
#include "PMXCharacterEquipmentComponent.h"
#include "ReferenceSkeleton.h"

namespace
{
float RotationAngleDeltaDegrees(const FQuat& A, const FQuat& B)
{
    return FMath::RadiansToDegrees(A.AngularDistance(B));
}

void AddAppliedMethod(TArray<FString>& Methods, const TCHAR* MethodName)
{
    Methods.AddUnique(MethodName);
}

FName NormalizeSlotName(FName SlotName)
{
    return SlotName.IsNone() ? TEXT("weapon") : SlotName;
}

void PrimeNiagaraComponentForCapture(
    UNiagaraComponent* NiagaraComponent,
    float DesiredAgeSeconds,
    float SeekDeltaSeconds,
    int32 AdvanceStepCount,
    float AdvanceStepDeltaSeconds,
    FPMXNiagaraCaptureWarmupEntry& Entry
)
{
    if (!NiagaraComponent)
    {
        Entry.Errors.Add(TEXT("niagara_component_missing"));
        return;
    }

    Entry.ComponentName = NiagaraComponent->GetName();
    if (UNiagaraSystem* NiagaraSystem = NiagaraComponent->GetAsset())
    {
        Entry.AssetPath = NiagaraSystem->GetPathName();
    }

    NiagaraComponent->SetAutoDestroy(false);
    AddAppliedMethod(Entry.AppliedMethods, TEXT("SetAutoDestroy"));

    NiagaraComponent->SetForceSolo(true);
    AddAppliedMethod(Entry.AppliedMethods, TEXT("SetForceSolo"));

    NiagaraComponent->SetPaused(false);
    AddAppliedMethod(Entry.AppliedMethods, TEXT("SetPaused"));

    NiagaraComponent->SetAutoActivate(true);
    AddAppliedMethod(Entry.AppliedMethods, TEXT("SetAutoActivate"));

    NiagaraComponent->SetRenderingEnabled(true);
    AddAppliedMethod(Entry.AppliedMethods, TEXT("SetRenderingEnabled"));

    NiagaraComponent->SetCanRenderWhileSeeking(true);
    AddAppliedMethod(Entry.AppliedMethods, TEXT("SetCanRenderWhileSeeking"));

    NiagaraComponent->SetAgeUpdateMode(ENiagaraAgeUpdateMode::DesiredAge);
    AddAppliedMethod(Entry.AppliedMethods, TEXT("SetAgeUpdateMode"));

    NiagaraComponent->SetSeekDelta(FMath::Max(SeekDeltaSeconds, 1.0f / 240.0f));
    AddAppliedMethod(Entry.AppliedMethods, TEXT("SetSeekDelta"));

    NiagaraComponent->SetLockDesiredAgeDeltaTimeToSeekDelta(false);
    AddAppliedMethod(Entry.AppliedMethods, TEXT("SetLockDesiredAgeDeltaTimeToSeekDelta"));

    NiagaraComponent->SetMaxSimTime(0.0f);
    AddAppliedMethod(Entry.AppliedMethods, TEXT("SetMaxSimTime"));

    NiagaraComponent->ResetSystem();
    AddAppliedMethod(Entry.AppliedMethods, TEXT("ResetSystem"));

    NiagaraComponent->ReinitializeSystem();
    AddAppliedMethod(Entry.AppliedMethods, TEXT("ReinitializeSystem"));

    NiagaraComponent->Activate(true);
    AddAppliedMethod(Entry.AppliedMethods, TEXT("Activate"));

    NiagaraComponent->SetDesiredAge(DesiredAgeSeconds);
    AddAppliedMethod(Entry.AppliedMethods, TEXT("SetDesiredAge"));

    NiagaraComponent->SeekToDesiredAge(DesiredAgeSeconds);
    AddAppliedMethod(Entry.AppliedMethods, TEXT("SeekToDesiredAge"));

    NiagaraComponent->TickComponent(FMath::Max(SeekDeltaSeconds, AdvanceStepDeltaSeconds), ELevelTick::LEVELTICK_All, nullptr);
    AddAppliedMethod(Entry.AppliedMethods, TEXT("TickComponent"));

    if (AdvanceStepCount > 0 && AdvanceStepDeltaSeconds > 0.0f)
    {
        NiagaraComponent->AdvanceSimulationByTime(AdvanceStepCount * AdvanceStepDeltaSeconds, AdvanceStepDeltaSeconds);
        AddAppliedMethod(Entry.AppliedMethods, TEXT("AdvanceSimulationByTime"));
    }

    NiagaraComponent->UpdateComponentToWorld();
    AddAppliedMethod(Entry.AppliedMethods, TEXT("UpdateComponentToWorld"));

    NiagaraComponent->UpdateBounds();
    AddAppliedMethod(Entry.AppliedMethods, TEXT("UpdateBounds"));

    NiagaraComponent->MarkRenderDynamicDataDirty();
    AddAppliedMethod(Entry.AppliedMethods, TEXT("MarkRenderDynamicDataDirty"));

    NiagaraComponent->MarkRenderStateDirty();
    AddAppliedMethod(Entry.AppliedMethods, TEXT("MarkRenderStateDirty"));

    Entry.Success = true;
}

TArray<FTransform> ResolveBaselineTransforms(USkeletalMeshComponent* MeshComponent, const FReferenceSkeleton& ReferenceSkeleton)
{
    TArray<FTransform> BaselineTransforms = MeshComponent ? MeshComponent->GetBoneSpaceTransforms() : TArray<FTransform>();
    if (BaselineTransforms.Num() != ReferenceSkeleton.GetNum())
    {
        BaselineTransforms = ReferenceSkeleton.GetRefBonePose();
    }
    return BaselineTransforms;
}
}

UPMXCharacterEquipmentComponent* UPMXEquipmentBlueprintLibrary::FindOrAddEquipmentComponent(AActor* Actor)
{
    if (!Actor)
    {
        return nullptr;
    }

    UPMXCharacterEquipmentComponent* Existing = Actor->FindComponentByClass<UPMXCharacterEquipmentComponent>();
    if (Existing)
    {
        return Existing;
    }

    UPMXCharacterEquipmentComponent* Created = NewObject<UPMXCharacterEquipmentComponent>(Actor, TEXT("PMXCharacterEquipmentComponent"));
    if (!Created)
    {
        return nullptr;
    }

    Created->RegisterComponent();
    Actor->AddInstanceComponent(Created);
    return Created;
}

bool UPMXEquipmentBlueprintLibrary::SetEquipmentAttachSocket(AActor* Actor, FName SocketName)
{
    return SetEquipmentAttachSocketForSlot(Actor, TEXT("weapon"), SocketName);
}

bool UPMXEquipmentBlueprintLibrary::SetEquipmentAttachSocketForSlot(AActor* Actor, FName SlotName, FName SocketName)
{
    UPMXCharacterEquipmentComponent* Component = FindOrAddEquipmentComponent(Actor);
    if (!Component)
    {
        return false;
    }

    if (SlotName.IsNone() || SlotName == TEXT("weapon"))
    {
        Component->SetAttachSocketName(SocketName);
        return true;
    }

    FPMXEquipmentSlotBindingEntry Binding;
    Binding.SlotName = SlotName;
    Binding.AttachSocketName = SocketName;
    Component->SetDesiredItemForSlot(Binding);
    return true;
}

USkeletalMeshComponent* UPMXEquipmentBlueprintLibrary::EquipWeaponMesh(AActor* Actor, USkeletalMesh* WeaponMesh)
{
    return EquipWeaponMeshToSocket(Actor, WeaponMesh, TEXT("WeaponSocket"));
}

USkeletalMeshComponent* UPMXEquipmentBlueprintLibrary::EquipWeaponMeshToSocket(AActor* Actor, USkeletalMesh* WeaponMesh, FName SocketName)
{
    UPMXCharacterEquipmentComponent* Component = FindOrAddEquipmentComponent(Actor);
    if (!Component)
    {
        return nullptr;
    }

    Component->SetAttachSocketName(SocketName);
    Component->SetDesiredWeaponMesh(WeaponMesh);
    return Component->ApplyWeaponMeshToOwner();
}

USceneComponent* UPMXEquipmentBlueprintLibrary::SetDesiredItemForSlot(AActor* Actor, const FPMXEquipmentSlotBindingEntry& SlotBinding)
{
    UPMXCharacterEquipmentComponent* Component = FindOrAddEquipmentComponent(Actor);
    if (!Component)
    {
        return nullptr;
    }

    Component->SetDesiredItemForSlot(SlotBinding);
    return Component->GetManagedComponentForSlot(SlotBinding.SlotName);
}

USceneComponent* UPMXEquipmentBlueprintLibrary::ApplyItemForSlot(AActor* Actor, const FPMXEquipmentSlotBindingEntry& SlotBinding)
{
    UPMXCharacterEquipmentComponent* Component = FindOrAddEquipmentComponent(Actor);
    if (!Component)
    {
        return nullptr;
    }

    Component->SetDesiredItemForSlot(SlotBinding);
    return Component->ApplyItemForSlot(SlotBinding.SlotName);
}

void UPMXEquipmentBlueprintLibrary::ApplySlotBindings(AActor* Actor, const TArray<FPMXEquipmentSlotBindingEntry>& SlotBindings)
{
    UPMXCharacterEquipmentComponent* Component = FindOrAddEquipmentComponent(Actor);
    if (!Component)
    {
        return;
    }

    for (const FPMXEquipmentSlotBindingEntry& Binding : SlotBindings)
    {
        Component->SetDesiredItemForSlot(Binding);
    }
    Component->ApplySlotBindings();
}

USceneComponent* UPMXEquipmentBlueprintLibrary::GetManagedComponentForSlot(AActor* Actor, FName SlotName)
{
    UPMXCharacterEquipmentComponent* Component = FindOrAddEquipmentComponent(Actor);
    if (!Component)
    {
        return nullptr;
    }

    return Component->GetManagedComponentForSlot(SlotName);
}

USkeletalMeshComponent* UPMXEquipmentBlueprintLibrary::ApplyEquipmentLoadout(AActor* Actor, UPMXEquipmentLoadoutAsset* LoadoutAsset)
{
    if (!Actor || !LoadoutAsset)
    {
        return nullptr;
    }

    UPMXCharacterEquipmentComponent* Component = FindOrAddEquipmentComponent(Actor);
    if (!Component)
    {
        return nullptr;
    }

    const FPMXEquipmentLoadoutEntry& Loadout = LoadoutAsset->Loadout;
    if (Loadout.SlotBindings.Num() > 0)
    {
        Component->SetDesiredSlotBindings(Loadout.SlotBindings);
        Component->ApplySlotBindings();
    }
    else
    {
        Component->SetAttachSocketName(Loadout.AttachSocketName);
        Component->SetDesiredWeaponMesh(Loadout.WeaponMesh);
        if (Loadout.WeaponMesh)
        {
            Component->ApplyWeaponMeshToOwner();
        }
    }
    return Component->GetManagedWeaponMeshComponent();
}

FPMXNiagaraCaptureWarmupResult UPMXEquipmentBlueprintLibrary::PrimeNiagaraForCapture(
    AActor* Actor,
    const TArray<FName>& SlotNames,
    float DesiredAgeSeconds,
    float SeekDeltaSeconds,
    int32 AdvanceStepCount,
    float AdvanceStepDeltaSeconds,
    bool bFlushWorld
)
{
    FPMXNiagaraCaptureWarmupResult Result;
    if (!Actor)
    {
        Result.Errors.Add(TEXT("actor_missing"));
        return Result;
    }

    UWorld* World = Actor->GetWorld();
    if (!World)
    {
        Result.Errors.Add(TEXT("world_missing"));
        return Result;
    }

    TArray<TPair<FName, UNiagaraComponent*>> ComponentsToWarm;
    TSet<UNiagaraComponent*> SeenComponents;
    TArray<FName> RequestedSlotNames = SlotNames;
    if (UPMXCharacterEquipmentComponent* EquipmentComponent = Actor->FindComponentByClass<UPMXCharacterEquipmentComponent>())
    {
        if (RequestedSlotNames.Num() == 0)
        {
            for (const FPMXEquipmentSlotBindingEntry& Binding : EquipmentComponent->GetDesiredSlotBindings())
            {
                RequestedSlotNames.AddUnique(NormalizeSlotName(Binding.SlotName));
            }
            for (const FPMXEquipmentSlotAttachState& AttachState : EquipmentComponent->GetResolvedSlotAttachStates())
            {
                RequestedSlotNames.AddUnique(NormalizeSlotName(AttachState.SlotName));
            }
        }

        for (const FName& SlotName : RequestedSlotNames)
        {
            const FName NormalizedSlotName = NormalizeSlotName(SlotName);
            if (UNiagaraComponent* NiagaraComponent = Cast<UNiagaraComponent>(EquipmentComponent->GetManagedComponentForSlot(NormalizedSlotName)))
            {
                if (!SeenComponents.Contains(NiagaraComponent))
                {
                    ComponentsToWarm.Add(TPair<FName, UNiagaraComponent*>(NormalizedSlotName, NiagaraComponent));
                    SeenComponents.Add(NiagaraComponent);
                }
            }
        }
    }

    Result.ComponentsRequested = RequestedSlotNames.Num();

    if (ComponentsToWarm.Num() == 0)
    {
        TInlineComponentArray<UNiagaraComponent*> NiagaraComponents(Actor);
        for (UNiagaraComponent* NiagaraComponent : NiagaraComponents)
        {
            if (!NiagaraComponent || SeenComponents.Contains(NiagaraComponent))
            {
                continue;
            }
            ComponentsToWarm.Add(TPair<FName, UNiagaraComponent*>(NAME_None, NiagaraComponent));
            SeenComponents.Add(NiagaraComponent);
        }
    }

    Result.ComponentsDiscovered = ComponentsToWarm.Num();

    for (const TPair<FName, UNiagaraComponent*>& EntryPair : ComponentsToWarm)
    {
        FPMXNiagaraCaptureWarmupEntry Entry;
        Entry.SlotName = EntryPair.Key;
        Entry.DesiredAgeSeconds = DesiredAgeSeconds;
        Entry.SeekDeltaSeconds = SeekDeltaSeconds;
        Entry.AdvanceStepCount = AdvanceStepCount;
        Entry.AdvanceStepDeltaSeconds = AdvanceStepDeltaSeconds;

        PrimeNiagaraComponentForCapture(
            EntryPair.Value,
            DesiredAgeSeconds,
            SeekDeltaSeconds,
            AdvanceStepCount,
            AdvanceStepDeltaSeconds,
            Entry
        );

        if (Entry.Success)
        {
            Result.ComponentsWarmed += 1;
        }
        Result.AppliedMethods.Append(Entry.AppliedMethods);
        Result.Warnings.Append(Entry.Warnings);
        Result.Errors.Append(Entry.Errors);
        Result.Entries.Add(Entry);
    }

    if (bFlushWorld)
    {
        const float WorldTickDeltaSeconds = FMath::Max(AdvanceStepDeltaSeconds, SeekDeltaSeconds);
        const int32 WorldTickIterations = FMath::Max(AdvanceStepCount, 1);
        FNiagaraWorldManager* NiagaraWorldManager = FNiagaraWorldManager::Get(World);

        for (int32 TickIndex = 0; TickIndex < WorldTickIterations; ++TickIndex)
        {
            World->Tick(ELevelTick::LEVELTICK_PauseTick, WorldTickDeltaSeconds);
            Result.AppliedMethods.AddUnique(TEXT("WorldTickPauseTick"));

            World->SendAllEndOfFrameUpdates();
            Result.AppliedMethods.AddUnique(TEXT("SendAllEndOfFrameUpdates"));

            if (NiagaraWorldManager)
            {
                NiagaraWorldManager->FlushComputeAndDeferredQueues(false);
                Result.AppliedMethods.AddUnique(TEXT("FlushComputeAndDeferredQueues"));
            }
        }

        if (!NiagaraWorldManager)
        {
            Result.Warnings.AddUnique(TEXT("niagara_world_manager_missing"));
        }
        Result.WorldFlushed = true;
    }

    Result.Success = Result.Errors.Num() == 0;
    return Result;
}

FPMXAnimationPoseEvaluationResult UPMXEquipmentBlueprintLibrary::EvaluateAnimationPoseOnComponent(
    USkeletalMeshComponent* MeshComponent,
    UAnimationAsset* AnimationAsset,
    float SampleTimeSeconds,
    const TArray<FName>& ProbeBoneNames
)
{
    FPMXAnimationPoseEvaluationResult Result;
    Result.SampleTimeSeconds = FMath::Max(0.0f, SampleTimeSeconds);

    if (!MeshComponent)
    {
        Result.Errors.Add(TEXT("mesh_component_missing"));
        return Result;
    }

    if (!AnimationAsset)
    {
        Result.Errors.Add(TEXT("animation_asset_missing"));
        return Result;
    }

    USkeletalMesh* SkeletalMesh = MeshComponent->GetSkeletalMeshAsset();
    if (!SkeletalMesh)
    {
        Result.Errors.Add(TEXT("skeletal_mesh_asset_missing"));
        return Result;
    }

    const FReferenceSkeleton& ReferenceSkeleton = SkeletalMesh->GetRefSkeleton();
    Result.BoneCount = ReferenceSkeleton.GetNum();
    if (Result.BoneCount <= 0)
    {
        Result.Errors.Add(TEXT("reference_skeleton_empty"));
        return Result;
    }

    TArray<FTransform> BaselineTransforms = ResolveBaselineTransforms(MeshComponent, ReferenceSkeleton);
    if (BaselineTransforms.Num() != Result.BoneCount)
    {
        Result.Errors.Add(TEXT("baseline_transform_count_mismatch"));
        return Result;
    }

    MeshComponent->bPauseAnims = false;
    MeshComponent->bNoSkeletonUpdate = false;
    MeshComponent->bUseRefPoseOnInitAnim = false;
    AddAppliedMethod(Result.AppliedMethods, TEXT("SetPreAnimationFlags"));

    MeshComponent->SetUpdateAnimationInEditor(true);
    AddAppliedMethod(Result.AppliedMethods, TEXT("SetUpdateAnimationInEditor"));

    MeshComponent->SetEnableAnimation(true);
    AddAppliedMethod(Result.AppliedMethods, TEXT("SetEnableAnimation"));

    MeshComponent->SetComponentTickEnabled(true);
    AddAppliedMethod(Result.AppliedMethods, TEXT("SetComponentTickEnabled"));

    MeshComponent->Activate(true);
    AddAppliedMethod(Result.AppliedMethods, TEXT("Activate"));

    MeshComponent->VisibilityBasedAnimTickOption = EVisibilityBasedAnimTickOption::AlwaysTickPoseAndRefreshBones;
    AddAppliedMethod(Result.AppliedMethods, TEXT("SetVisibilityBasedAnimTickOption"));

    MeshComponent->SetAnimationMode(EAnimationMode::AnimationSingleNode, true);
    AddAppliedMethod(Result.AppliedMethods, TEXT("SetAnimationMode"));

    MeshComponent->OverrideAnimationData(AnimationAsset, false, true, Result.SampleTimeSeconds, 1.0f);
    AddAppliedMethod(Result.AppliedMethods, TEXT("OverrideAnimationData"));

    MeshComponent->SetAnimation(AnimationAsset);
    AddAppliedMethod(Result.AppliedMethods, TEXT("SetAnimation"));

    MeshComponent->SetPlayRate(1.0f);
    AddAppliedMethod(Result.AppliedMethods, TEXT("SetPlayRate"));

    MeshComponent->Play(false);
    AddAppliedMethod(Result.AppliedMethods, TEXT("Play"));

    MeshComponent->SetPosition(Result.SampleTimeSeconds, false);
    AddAppliedMethod(Result.AppliedMethods, TEXT("SetPosition"));

    MeshComponent->TickAnimation(0.0f, false);
    AddAppliedMethod(Result.AppliedMethods, TEXT("TickAnimation"));

    MeshComponent->TickPose(0.0f, false);
    AddAppliedMethod(Result.AppliedMethods, TEXT("TickPose"));

    MeshComponent->RefreshBoneTransforms(nullptr);
    AddAppliedMethod(Result.AppliedMethods, TEXT("RefreshBoneTransforms"));

    MeshComponent->UpdateComponentToWorld();
    AddAppliedMethod(Result.AppliedMethods, TEXT("UpdateComponentToWorld"));

    MeshComponent->UpdateBounds();
    AddAppliedMethod(Result.AppliedMethods, TEXT("UpdateBounds"));

    MeshComponent->MarkRenderTransformDirty();
    AddAppliedMethod(Result.AppliedMethods, TEXT("MarkRenderTransformDirty"));

    MeshComponent->MarkRenderDynamicDataDirty();
    AddAppliedMethod(Result.AppliedMethods, TEXT("MarkRenderDynamicDataDirty"));

    const TArray<FTransform> AfterTransforms = MeshComponent->GetBoneSpaceTransforms();
    if (AfterTransforms.Num() != Result.BoneCount)
    {
        Result.Errors.Add(TEXT("after_transform_count_mismatch"));
        return Result;
    }

    constexpr float LocationThreshold = 0.001f;
    constexpr float RotationThresholdDegrees = 0.05f;
    constexpr float ScaleThreshold = 0.001f;

    for (int32 BoneIndex = 0; BoneIndex < Result.BoneCount; ++BoneIndex)
    {
        const FTransform& BeforeTransform = BaselineTransforms[BoneIndex];
        const FTransform& AfterTransform = AfterTransforms[BoneIndex];
        const float LocationDelta = FVector::Dist(BeforeTransform.GetLocation(), AfterTransform.GetLocation());
        const float RotationDelta = RotationAngleDeltaDegrees(BeforeTransform.GetRotation(), AfterTransform.GetRotation());
        const float ScaleDelta = FVector::Dist(BeforeTransform.GetScale3D(), AfterTransform.GetScale3D());

        Result.MaxLocationDelta = FMath::Max(Result.MaxLocationDelta, LocationDelta);
        Result.MaxRotationAngleDeltaDegrees = FMath::Max(Result.MaxRotationAngleDeltaDegrees, RotationDelta);
        Result.MaxScaleDelta = FMath::Max(Result.MaxScaleDelta, ScaleDelta);

        if (LocationDelta > LocationThreshold || RotationDelta > RotationThresholdDegrees || ScaleDelta > ScaleThreshold)
        {
            Result.ChangedBoneCount += 1;
        }
    }

    for (const FName& ProbeBoneName : ProbeBoneNames)
    {
        FPMXAnimationPoseProbeResult ProbeResult;
        ProbeResult.BoneName = ProbeBoneName;
        const int32 BoneIndex = ReferenceSkeleton.FindBoneIndex(ProbeBoneName);
        if (BoneIndex == INDEX_NONE)
        {
            Result.Warnings.Add(FString::Printf(TEXT("probe_bone_missing:%s"), *ProbeBoneName.ToString()));
            Result.ProbeResults.Add(ProbeResult);
            continue;
        }

        ProbeResult.Found = true;
        const FTransform& BeforeTransform = BaselineTransforms[BoneIndex];
        const FTransform& AfterTransform = AfterTransforms[BoneIndex];
        ProbeResult.LocationDelta = FVector::Dist(BeforeTransform.GetLocation(), AfterTransform.GetLocation());
        ProbeResult.RotationAngleDeltaDegrees = RotationAngleDeltaDegrees(BeforeTransform.GetRotation(), AfterTransform.GetRotation());
        ProbeResult.ScaleDelta = FVector::Dist(BeforeTransform.GetScale3D(), AfterTransform.GetScale3D());
        ProbeResult.Changed =
            ProbeResult.LocationDelta > LocationThreshold ||
            ProbeResult.RotationAngleDeltaDegrees > RotationThresholdDegrees ||
            ProbeResult.ScaleDelta > ScaleThreshold;
        Result.ProbeResults.Add(ProbeResult);
    }

    Result.PoseChanged = Result.ChangedBoneCount > 0;
    Result.Success = true;
    if (!Result.PoseChanged)
    {
        Result.Warnings.Add(TEXT("native_pose_unchanged_after_evaluation"));
    }
    return Result;
}
