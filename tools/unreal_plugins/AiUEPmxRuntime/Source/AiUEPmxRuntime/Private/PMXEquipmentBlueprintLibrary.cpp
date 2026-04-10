#include "PMXEquipmentBlueprintLibrary.h"

#include "Animation/AnimationAsset.h"
#include "Components/SkeletalMeshComponent.h"
#include "GameFramework/Actor.h"
#include "PMXCharacterEquipmentComponent.h"
#include "PMXEquipmentReflection.h"

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
    UPMXCharacterEquipmentComponent* Component = FindOrAddEquipmentComponent(Actor);
    if (!Component)
    {
        return false;
    }

    Component->SetAttachSocketName(SocketName);
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

USkeletalMeshComponent* UPMXEquipmentBlueprintLibrary::ApplyEquipmentLoadout(AActor* Actor, UPMXEquipmentLoadoutAsset* LoadoutAsset)
{
    if (!LoadoutAsset)
    {
        return nullptr;
    }

    const FPMXEquipmentLoadoutEntry& Loadout = LoadoutAsset->Loadout;
    return EquipWeaponMeshToSocket(Actor, Loadout.WeaponMesh, Loadout.AttachSocketName);
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
