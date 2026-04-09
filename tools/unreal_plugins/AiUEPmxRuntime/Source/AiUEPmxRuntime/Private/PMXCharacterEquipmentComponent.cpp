#include "PMXCharacterEquipmentComponent.h"

#include "Components/SkeletalMeshComponent.h"
#include "Engine/EngineTypes.h"
#include "GameFramework/Actor.h"
#include "ReferenceSkeleton.h"

namespace
{
TArray<FName> BuildAttachCandidates(FName RequestedName)
{
    TArray<FName> Candidates;
    auto AddCandidate = [&Candidates](const TCHAR* Name)
    {
        const FName Candidate(Name);
        if (!Candidate.IsNone())
        {
            Candidates.AddUnique(Candidate);
        }
    };

    if (!RequestedName.IsNone())
    {
        Candidates.AddUnique(RequestedName);
    }

    AddCandidate(TEXT("WeaponSocket"));
    AddCandidate(TEXT("weapon_socket"));
    AddCandidate(TEXT("Hand_R_Weapon"));
    AddCandidate(TEXT("RightHandSocket"));
    AddCandidate(TEXT("hand_r_socket"));
    AddCandidate(TEXT("hand_r"));
    AddCandidate(TEXT("Hand_R"));
    AddCandidate(TEXT("r_hand"));
    AddCandidate(TEXT("R_Hand"));
    AddCandidate(TEXT("RightHand"));
    AddCandidate(TEXT("right_hand"));
    AddCandidate(TEXT("ik_hand_r"));

    return Candidates;
}

bool MatchesAttachPattern(const FString& Name)
{
    const FString Lower = Name.ToLower();
    return Lower.Contains(TEXT("weapon"))
        || Lower.Contains(TEXT("wpn"))
        || Lower.Contains(TEXT("hand_r"))
        || Lower.Contains(TEXT("r_hand"))
        || Lower.Contains(TEXT("righthand"))
        || Lower.Contains(TEXT("right_hand"))
        || Lower.Contains(TEXT("handr"));
}

int32 ScoreFallbackBoneName(const FString& Name)
{
    const FString Lower = Name.ToLower();
    int32 Score = 0;

    if (Lower.Contains(TEXT("weapon")))
    {
        Score += 100;
    }
    if (Lower.Contains(TEXT("hand_r")) || Lower.Contains(TEXT("r_hand")) || Lower.Contains(TEXT("right_hand")) || Lower.Contains(TEXT("righthand")))
    {
        Score += 90;
    }
    if (Lower.Contains(TEXT("dummy_d_r")))
    {
        Score += 70;
    }
    if (Lower.Contains(TEXT("dummy")) && Lower.Contains(TEXT("_r")))
    {
        Score += 55;
    }
    if (Lower.Contains(TEXT("_r_")) || Lower.EndsWith(TEXT("_r")) || Lower.Contains(TEXT("right")))
    {
        Score += 40;
    }
    if (Lower.Contains(TEXT("shadow")))
    {
        Score -= 20;
    }
    if (Lower.Contains(TEXT("view")) || Lower.Contains(TEXT("groove")) || Lower.Contains(TEXT("waist")))
    {
        Score -= 10;
    }

    return Score;
}
}

UPMXCharacterEquipmentComponent::UPMXCharacterEquipmentComponent()
{
    PrimaryComponentTick.bCanEverTick = false;
}

void UPMXCharacterEquipmentComponent::BeginPlay()
{
    Super::BeginPlay();

    if (DesiredWeaponMesh)
    {
        ApplyWeaponMeshToOwner();
    }
}

void UPMXCharacterEquipmentComponent::SetDesiredWeaponMesh(USkeletalMesh* InWeaponMesh)
{
    DesiredWeaponMesh = InWeaponMesh;
}

USkeletalMesh* UPMXCharacterEquipmentComponent::GetDesiredWeaponMesh() const
{
    return DesiredWeaponMesh;
}

void UPMXCharacterEquipmentComponent::SetAttachSocketName(FName InAttachSocketName)
{
    AttachSocketName = InAttachSocketName.IsNone() ? TEXT("WeaponSocket") : InAttachSocketName;

    if (ManagedWeaponMeshComponent)
    {
        ApplyWeaponMeshToOwner();
    }
}

FName UPMXCharacterEquipmentComponent::GetAttachSocketName() const
{
    return AttachSocketName;
}

USkeletalMeshComponent* UPMXCharacterEquipmentComponent::GetManagedWeaponMeshComponent() const
{
    return ManagedWeaponMeshComponent;
}

FName UPMXCharacterEquipmentComponent::GetResolvedAttachSocketName() const
{
    return ResolvedAttachSocketName;
}

bool UPMXCharacterEquipmentComponent::HasResolvedAttachSocket() const
{
    return bResolvedAttachSocketExists;
}

FString UPMXCharacterEquipmentComponent::GetAttachResolutionMode() const
{
    return AttachResolutionMode;
}

USkeletalMeshComponent* UPMXCharacterEquipmentComponent::FindOwnerMeshComponent() const
{
    if (const AActor* Owner = GetOwner())
    {
        return Owner->FindComponentByClass<USkeletalMeshComponent>();
    }
    return nullptr;
}

FName UPMXCharacterEquipmentComponent::ResolveAttachSocketName(USkeletalMeshComponent* OwnerMesh)
{
    ResolvedAttachSocketName = NAME_None;
    bResolvedAttachSocketExists = false;
    AttachResolutionMode = TEXT("owner_origin");

    if (!OwnerMesh)
    {
        AttachResolutionMode = TEXT("owner_mesh_missing");
        return NAME_None;
    }

    const TArray<FName> Candidates = BuildAttachCandidates(AttachSocketName);
    for (const FName& Candidate : Candidates)
    {
        if (!Candidate.IsNone() && OwnerMesh->DoesSocketExist(Candidate))
        {
            ResolvedAttachSocketName = Candidate;
            bResolvedAttachSocketExists = true;
            AttachResolutionMode = Candidate == AttachSocketName ? TEXT("requested_socket") : TEXT("fallback_socket");
            return Candidate;
        }
    }

    if (const USkeletalMesh* OwnerMeshAsset = OwnerMesh->GetSkeletalMeshAsset())
    {
        const FReferenceSkeleton& ReferenceSkeleton = OwnerMeshAsset->GetRefSkeleton();
        const int32 BoneCount = ReferenceSkeleton.GetNum();
        FName BestBoneName = NAME_None;
        int32 BestBoneScore = 0;
        for (int32 BoneIndex = 0; BoneIndex < BoneCount; ++BoneIndex)
        {
            const FName BoneName = ReferenceSkeleton.GetBoneName(BoneIndex);
            const FString BoneNameString = BoneName.ToString();
            if (MatchesAttachPattern(BoneNameString))
            {
                ResolvedAttachSocketName = BoneName;
                bResolvedAttachSocketExists = true;
                AttachResolutionMode = TEXT("fallback_bone_pattern");
                return BoneName;
            }

            const int32 BoneScore = ScoreFallbackBoneName(BoneNameString);
            if (BoneScore >= BestBoneScore)
            {
                BestBoneScore = BoneScore;
                BestBoneName = BoneName;
            }
        }

        if (!BestBoneName.IsNone() && BestBoneScore > 0)
        {
            ResolvedAttachSocketName = BestBoneName;
            bResolvedAttachSocketExists = true;
            AttachResolutionMode = TEXT("fallback_bone_score");
            return BestBoneName;
        }
    }

    return NAME_None;
}

void UPMXCharacterEquipmentComponent::RefreshManagedMeshComponent(USkeletalMeshComponent* MeshComponent) const
{
    if (!MeshComponent)
    {
        return;
    }

    MeshComponent->SetVisibility(true, true);
    MeshComponent->SetHiddenInGame(false, true);
    MeshComponent->SetCastShadow(true);
    MeshComponent->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    MeshComponent->SetRelativeLocationAndRotation(FVector::ZeroVector, FRotator::ZeroRotator);
    MeshComponent->RefreshBoneTransforms();
    MeshComponent->UpdateBounds();
    MeshComponent->MarkRenderTransformDirty();
    MeshComponent->MarkRenderDynamicDataDirty();
    MeshComponent->MarkRenderStateDirty();
}

USkeletalMeshComponent* UPMXCharacterEquipmentComponent::EnsureManagedMeshComponent()
{
    if (ManagedWeaponMeshComponent)
    {
        return ManagedWeaponMeshComponent;
    }

    AActor* Owner = GetOwner();
    if (!Owner)
    {
        return nullptr;
    }

    TInlineComponentArray<USkeletalMeshComponent*> SkeletalMeshComponents(Owner);
    if (SkeletalMeshComponents.Num() > 1)
    {
        ManagedWeaponMeshComponent = SkeletalMeshComponents[1];
        return ManagedWeaponMeshComponent;
    }

    if (!bCreateComponentIfMissing)
    {
        return nullptr;
    }

    USkeletalMeshComponent* OwnerMesh = FindOwnerMeshComponent();
    if (!OwnerMesh)
    {
        return nullptr;
    }

    if (ManagedWeaponMeshComponent)
    {
        ManagedWeaponMeshComponent->AttachToComponent(
            OwnerMesh,
            FAttachmentTransformRules::SnapToTargetNotIncludingScale,
            AttachSocketName
        );
        return ManagedWeaponMeshComponent;
    }

    ManagedWeaponMeshComponent = NewObject<USkeletalMeshComponent>(Owner, TEXT("DefaultWeaponMeshComponent"));
    if (!ManagedWeaponMeshComponent)
    {
        return nullptr;
    }

    ManagedWeaponMeshComponent->SetupAttachment(OwnerMesh, AttachSocketName);
    ManagedWeaponMeshComponent->RegisterComponent();
    Owner->AddInstanceComponent(ManagedWeaponMeshComponent);
    RefreshManagedMeshComponent(ManagedWeaponMeshComponent);
    return ManagedWeaponMeshComponent;
}

USkeletalMeshComponent* UPMXCharacterEquipmentComponent::ApplyWeaponMeshToOwner()
{
    USkeletalMeshComponent* MeshComponent = EnsureManagedMeshComponent();
    if (!MeshComponent)
    {
        return nullptr;
    }

    if (AActor* Owner = GetOwner())
    {
        if (USkeletalMeshComponent* OwnerMesh = FindOwnerMeshComponent())
        {
            const FName TargetAttachName = ResolveAttachSocketName(OwnerMesh);
            MeshComponent->AttachToComponent(
                OwnerMesh,
                FAttachmentTransformRules::SnapToTargetNotIncludingScale,
                TargetAttachName
            );
        }
    }

    MeshComponent->SetSkeletalMesh(DesiredWeaponMesh);
    RefreshManagedMeshComponent(MeshComponent);
    return MeshComponent;
}
