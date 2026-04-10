#include "PMXCharacterEquipmentComponent.h"

#include "Components/PrimitiveComponent.h"
#include "Components/SceneComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/EngineTypes.h"
#include "GameFramework/Actor.h"
#include "ReferenceSkeleton.h"

namespace
{
const FName WeaponSlotName(TEXT("weapon"));
const FString SkeletalMeshItemKind(TEXT("skeletal_mesh"));
const FString StaticMeshItemKind(TEXT("static_mesh"));

FName NormalizeSlotName(FName SlotName)
{
    return SlotName.IsNone() ? WeaponSlotName : SlotName;
}

FString SanitizeSlotToken(FName SlotName)
{
    const FString Raw = NormalizeSlotName(SlotName).ToString();
    FString Result;
    Result.Reserve(Raw.Len());
    for (const TCHAR Character : Raw)
    {
        if (FChar::IsAlnum(Character))
        {
            Result.AppendChar(Character);
        }
        else
        {
            Result.AppendChar(TEXT('_'));
        }
    }
    Result.ReplaceInline(TEXT("__"), TEXT("_"));
    Result.TrimStartAndEndInline();
    return Result.IsEmpty() ? TEXT("Slot") : Result;
}

bool IsStaticMeshKind(const FString& ItemKind)
{
    return ItemKind.Equals(StaticMeshItemKind, ESearchCase::IgnoreCase)
        || ItemKind.Equals(TEXT("static"), ESearchCase::IgnoreCase);
}

bool IsSkeletalMeshKind(const FString& ItemKind)
{
    return ItemKind.Equals(SkeletalMeshItemKind, ESearchCase::IgnoreCase)
        || ItemKind.Equals(TEXT("skeletal"), ESearchCase::IgnoreCase)
        || ItemKind.Equals(TEXT("skeletalmesh"), ESearchCase::IgnoreCase);
}

FString ComponentAssetPath(USceneComponent* Component)
{
    if (!Component)
    {
        return FString();
    }

    if (USkeletalMeshComponent* SkeletalMeshComponent = Cast<USkeletalMeshComponent>(Component))
    {
        if (USkeletalMesh* SkeletalMesh = SkeletalMeshComponent->GetSkeletalMeshAsset())
        {
            return SkeletalMesh->GetPathName();
        }
    }

    if (UStaticMeshComponent* StaticMeshComponent = Cast<UStaticMeshComponent>(Component))
    {
        if (UStaticMesh* StaticMesh = StaticMeshComponent->GetStaticMesh())
        {
            return StaticMesh->GetPathName();
        }
    }

    return FString();
}

bool IsWearableSlotProfile(FName SlotName, FName RequestedName)
{
    const FString SlotLower = NormalizeSlotName(SlotName).ToString().ToLower();
    const FString RequestedLower = RequestedName.ToString().ToLower();
    auto ContainsWearableToken = [](const FString& Text)
    {
        return Text.Contains(TEXT("cloth"))
            || Text.Contains(TEXT("clothing"))
            || Text.Contains(TEXT("hair"))
            || Text.Contains(TEXT("head"))
            || Text.Contains(TEXT("neck"))
            || Text.Contains(TEXT("scarf"))
            || Text.Contains(TEXT("skirt"))
            || Text.Contains(TEXT("cape"))
            || Text.Contains(TEXT("hood"))
            || Text.Contains(TEXT("hat"))
            || Text.Contains(TEXT("top"))
            || Text.Contains(TEXT("shirt"))
            || Text.Contains(TEXT("pants"))
            || Text.Contains(TEXT("pouch"))
            || Text.Contains(TEXT("canister"))
            || Text.Contains(TEXT("shoulder"))
            || Text.Contains(TEXT("wear"));
    };
    return ContainsWearableToken(SlotLower) || ContainsWearableToken(RequestedLower);
}

TArray<FName> BuildAttachCandidates(FName RequestedName, FName SlotName)
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

    if (IsWearableSlotProfile(SlotName, RequestedName))
    {
        AddCandidate(TEXT("Head"));
        AddCandidate(TEXT("head"));
        AddCandidate(TEXT("HeadSocket"));
        AddCandidate(TEXT("head_socket"));
        AddCandidate(TEXT("HairSocket"));
        AddCandidate(TEXT("hair_socket"));
        AddCandidate(TEXT("Neck"));
        AddCandidate(TEXT("neck"));
        AddCandidate(TEXT("Neck_01"));
        AddCandidate(TEXT("neck_01"));
        AddCandidate(TEXT("Spine_03"));
        AddCandidate(TEXT("spine_03"));
        AddCandidate(TEXT("Spine_02"));
        AddCandidate(TEXT("spine_02"));
        AddCandidate(TEXT("upperchest"));
        AddCandidate(TEXT("UpperChest"));
        AddCandidate(TEXT("Chest"));
        AddCandidate(TEXT("chest"));
        AddCandidate(TEXT("clavicle_l"));
        AddCandidate(TEXT("clavicle_r"));
        AddCandidate(TEXT("BackSocket"));
        AddCandidate(TEXT("back_socket"));
        return Candidates;
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

bool MatchesAttachPattern(const FString& Name, FName SlotName, FName RequestedName)
{
    const FString Lower = Name.ToLower();
    if (IsWearableSlotProfile(SlotName, RequestedName))
    {
        return Lower.Contains(TEXT("head"))
            || Lower.Contains(TEXT("hair"))
            || Lower.Contains(TEXT("neck"))
            || Lower.Contains(TEXT("upperchest"))
            || Lower.Contains(TEXT("chest"))
            || Lower.Contains(TEXT("clavicle"))
            || Lower.Contains(TEXT("spine_03"))
            || Lower.Contains(TEXT("spine03"))
            || Lower.Contains(TEXT("spine_02"))
            || Lower.Contains(TEXT("spine02"))
            || Lower.Contains(TEXT("shoulder"));
    }
    return Lower.Contains(TEXT("weapon"))
        || Lower.Contains(TEXT("wpn"))
        || Lower.Contains(TEXT("hand_r"))
        || Lower.Contains(TEXT("r_hand"))
        || Lower.Contains(TEXT("righthand"))
        || Lower.Contains(TEXT("right_hand"))
        || Lower.Contains(TEXT("handr"));
}

int32 ScoreFallbackBoneName(const FString& Name, FName SlotName, FName RequestedName)
{
    const FString Lower = Name.ToLower();
    int32 Score = 0;

    if (IsWearableSlotProfile(SlotName, RequestedName))
    {
        if (Lower.Contains(TEXT("head")))
        {
            Score += 120;
        }
        if (Lower.Contains(TEXT("hair")))
        {
            Score += 100;
        }
        if (Lower.Contains(TEXT("neck")))
        {
            Score += 90;
        }
        if (Lower.Contains(TEXT("upperchest")) || Lower.Contains(TEXT("chest")))
        {
            Score += 70;
        }
        if (Lower.Contains(TEXT("clavicle")) || Lower.Contains(TEXT("shoulder")))
        {
            Score += 60;
        }
        if (Lower.Contains(TEXT("spine_03")) || Lower.Contains(TEXT("spine03")) || Lower.Contains(TEXT("spine_02")) || Lower.Contains(TEXT("spine02")))
        {
            Score += 55;
        }
        if (Lower.Contains(TEXT("spine")))
        {
            Score += 30;
        }
        if (Lower.Contains(TEXT("weapon")) || Lower.Contains(TEXT("wpn")))
        {
            Score -= 120;
        }
        if (Lower.Contains(TEXT("hand_r")) || Lower.Contains(TEXT("r_hand")) || Lower.Contains(TEXT("right_hand")) || Lower.Contains(TEXT("righthand")) || Lower.Contains(TEXT("ik_hand_r")))
        {
            Score -= 100;
        }
        if (Lower.Contains(TEXT("dummy_d_r")) || ((Lower.Contains(TEXT("dummy")) && Lower.Contains(TEXT("_r"))) || Lower.Contains(TEXT("_r_")) || Lower.EndsWith(TEXT("_r"))))
        {
            Score -= 75;
        }
        if (Lower.Contains(TEXT("shadow")))
        {
            Score -= 20;
        }
        return Score;
    }

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

    if (DesiredSlotBindings.Num() > 0 || DesiredWeaponMesh)
    {
        ApplySlotBindings();
    }
}

void UPMXCharacterEquipmentComponent::MirrorLegacyWeaponState()
{
    const int32 WeaponBindingIndex = FindSlotBindingIndex(WeaponSlotName);
    if (WeaponBindingIndex != INDEX_NONE)
    {
        const FPMXEquipmentSlotBindingEntry& WeaponBinding = DesiredSlotBindings[WeaponBindingIndex];
        DesiredWeaponMesh = WeaponBinding.SkeletalMesh;
        AttachSocketName = WeaponBinding.AttachSocketName.IsNone() ? TEXT("WeaponSocket") : WeaponBinding.AttachSocketName;
    }
    else
    {
        DesiredWeaponMesh = nullptr;
        AttachSocketName = TEXT("WeaponSocket");
    }

    if (const FPMXEquipmentSlotAttachState* WeaponAttachState = FindSlotAttachState(WeaponSlotName))
    {
        ResolvedAttachSocketName = WeaponAttachState->ResolvedAttachSocketName;
        bResolvedAttachSocketExists = WeaponAttachState->bResolvedAttachSocketExists;
        AttachResolutionMode = WeaponAttachState->AttachResolutionMode;
    }
    else
    {
        ResolvedAttachSocketName = NAME_None;
        bResolvedAttachSocketExists = false;
        AttachResolutionMode = TEXT("unresolved");
    }
}

int32 UPMXCharacterEquipmentComponent::FindSlotBindingIndex(FName SlotName) const
{
    const FName NormalizedSlotName = NormalizeSlotName(SlotName);
    for (int32 Index = 0; Index < DesiredSlotBindings.Num(); ++Index)
    {
        if (NormalizeSlotName(DesiredSlotBindings[Index].SlotName) == NormalizedSlotName)
        {
            return Index;
        }
    }
    return INDEX_NONE;
}

void UPMXCharacterEquipmentComponent::RecordSlotConflict(
    const FPMXEquipmentSlotBindingEntry& PreviousBinding,
    const FPMXEquipmentSlotBindingEntry& IncomingBinding
)
{
    FPMXEquipmentSlotConflictEntry Conflict;
    Conflict.SlotName = NormalizeSlotName(IncomingBinding.SlotName);
    Conflict.PreviousItemPackageId = PreviousBinding.ItemPackageId;
    Conflict.IncomingItemPackageId = IncomingBinding.ItemPackageId;
    Conflict.PreviousItemKind = NormalizeItemKind(PreviousBinding.ItemKind, PreviousBinding);
    Conflict.IncomingItemKind = NormalizeItemKind(IncomingBinding.ItemKind, IncomingBinding);
    Conflict.PreviousAttachSocketName = PreviousBinding.AttachSocketName;
    Conflict.IncomingAttachSocketName = IncomingBinding.AttachSocketName;
    SlotConflicts.Add(Conflict);
}

FPMXEquipmentSlotBindingEntry UPMXCharacterEquipmentComponent::BuildWeaponBinding(USkeletalMesh* InWeaponMesh) const
{
    FPMXEquipmentSlotBindingEntry Binding;
    Binding.SlotName = WeaponSlotName;
    Binding.ItemKind = SkeletalMeshItemKind;
    Binding.AttachSocketName = AttachSocketName.IsNone() ? TEXT("WeaponSocket") : AttachSocketName;
    Binding.SkeletalMesh = InWeaponMesh;
    Binding.bConsumerReady = (InWeaponMesh != nullptr);
    return Binding;
}

FString UPMXCharacterEquipmentComponent::NormalizeItemKind(const FString& ItemKind, const FPMXEquipmentSlotBindingEntry& Binding) const
{
    if (Binding.StaticMesh)
    {
        return StaticMeshItemKind;
    }
    if (Binding.SkeletalMesh)
    {
        return SkeletalMeshItemKind;
    }
    if (IsStaticMeshKind(ItemKind))
    {
        return StaticMeshItemKind;
    }
    if (IsSkeletalMeshKind(ItemKind))
    {
        return SkeletalMeshItemKind;
    }
    return SkeletalMeshItemKind;
}

FPMXEquipmentSlotAttachState* UPMXCharacterEquipmentComponent::FindSlotAttachState(FName SlotName)
{
    const FName NormalizedSlotName = NormalizeSlotName(SlotName);
    return SlotAttachStates.FindByPredicate(
        [NormalizedSlotName](const FPMXEquipmentSlotAttachState& Entry)
        {
            return NormalizeSlotName(Entry.SlotName) == NormalizedSlotName;
        }
    );
}

const FPMXEquipmentSlotAttachState* UPMXCharacterEquipmentComponent::FindSlotAttachState(FName SlotName) const
{
    const FName NormalizedSlotName = NormalizeSlotName(SlotName);
    return SlotAttachStates.FindByPredicate(
        [NormalizedSlotName](const FPMXEquipmentSlotAttachState& Entry)
        {
            return NormalizeSlotName(Entry.SlotName) == NormalizedSlotName;
        }
    );
}

FPMXEquipmentSlotAttachState& UPMXCharacterEquipmentComponent::UpsertSlotAttachState(FName SlotName)
{
    const FName NormalizedSlotName = NormalizeSlotName(SlotName);
    if (FPMXEquipmentSlotAttachState* Existing = FindSlotAttachState(NormalizedSlotName))
    {
        return *Existing;
    }

    FPMXEquipmentSlotAttachState& Added = SlotAttachStates.AddDefaulted_GetRef();
    Added.SlotName = NormalizedSlotName;
    return Added;
}

FName UPMXCharacterEquipmentComponent::ManagedComponentNameForSlot(FName SlotName, const FString& NormalizedItemKind) const
{
    const FName NormalizedSlotName = NormalizeSlotName(SlotName);
    if (NormalizedSlotName == WeaponSlotName)
    {
        return TEXT("DefaultWeaponMeshComponent");
    }

    const FString Suffix = IsStaticMeshKind(NormalizedItemKind) ? TEXT("StaticMeshComponent") : TEXT("SkeletalMeshComponent");
    return FName(*FString::Printf(TEXT("PMXSlot_%s_%s"), *SanitizeSlotToken(NormalizedSlotName), *Suffix));
}

USceneComponent* UPMXCharacterEquipmentComponent::FindExistingManagedComponent(FName SlotName, const FString& NormalizedItemKind) const
{
    AActor* Owner = GetOwner();
    if (!Owner)
    {
        return nullptr;
    }

    const FName ExpectedName = ManagedComponentNameForSlot(SlotName, NormalizedItemKind);
    if (IsStaticMeshKind(NormalizedItemKind))
    {
        TInlineComponentArray<UStaticMeshComponent*> Components(Owner);
        for (UStaticMeshComponent* Component : Components)
        {
            if (Component && Component->GetFName() == ExpectedName)
            {
                return Component;
            }
        }
        return nullptr;
    }

    TInlineComponentArray<USkeletalMeshComponent*> Components(Owner);
    for (USkeletalMeshComponent* Component : Components)
    {
        if (Component && Component->GetFName() == ExpectedName)
        {
            return Component;
        }
    }

    if (NormalizeSlotName(SlotName) == WeaponSlotName)
    {
        USkeletalMeshComponent* OwnerMesh = FindOwnerMeshComponent();
        for (USkeletalMeshComponent* Component : Components)
        {
            if (Component && Component != OwnerMesh && Component->GetSkeletalMeshAsset())
            {
                return Component;
            }
        }
    }

    return nullptr;
}

USceneComponent* UPMXCharacterEquipmentComponent::EnsureManagedComponentForSlot(
    const FPMXEquipmentSlotBindingEntry& Binding,
    const FString& NormalizedItemKind
)
{
    const FName SlotName = NormalizeSlotName(Binding.SlotName);
    USceneComponent* ExistingComponent = nullptr;
    if (TObjectPtr<USceneComponent>* ExistingEntry = ManagedComponentsBySlot.Find(SlotName))
    {
        ExistingComponent = ExistingEntry->Get();
    }

    const bool WantsStaticMesh = IsStaticMeshKind(NormalizedItemKind);
    const bool HasCompatibleExisting =
        (WantsStaticMesh && Cast<UStaticMeshComponent>(ExistingComponent) != nullptr)
        || (!WantsStaticMesh && Cast<USkeletalMeshComponent>(ExistingComponent) != nullptr);

    if (!HasCompatibleExisting && ExistingComponent)
    {
        ExistingComponent->DestroyComponent();
        ManagedComponentsBySlot.Remove(SlotName);
        ExistingComponent = nullptr;
    }

    if (!ExistingComponent)
    {
        ExistingComponent = FindExistingManagedComponent(SlotName, NormalizedItemKind);
        if (ExistingComponent)
        {
            ManagedComponentsBySlot.Add(SlotName, ExistingComponent);
            return ExistingComponent;
        }
    }

    if (ExistingComponent)
    {
        return ExistingComponent;
    }

    if (!bCreateComponentIfMissing)
    {
        return nullptr;
    }

    AActor* Owner = GetOwner();
    USkeletalMeshComponent* OwnerMesh = FindOwnerMeshComponent();
    if (!Owner || !OwnerMesh)
    {
        return nullptr;
    }

    const FName ComponentName = ManagedComponentNameForSlot(SlotName, NormalizedItemKind);
    USceneComponent* CreatedComponent = nullptr;
    if (WantsStaticMesh)
    {
        UStaticMeshComponent* StaticMeshComponent = NewObject<UStaticMeshComponent>(Owner, ComponentName);
        CreatedComponent = StaticMeshComponent;
    }
    else
    {
        USkeletalMeshComponent* SkeletalMeshComponent = NewObject<USkeletalMeshComponent>(Owner, ComponentName);
        CreatedComponent = SkeletalMeshComponent;
    }

    if (!CreatedComponent)
    {
        return nullptr;
    }

    CreatedComponent->SetupAttachment(OwnerMesh, Binding.AttachSocketName);
    CreatedComponent->RegisterComponent();
    Owner->AddInstanceComponent(CreatedComponent);
    RefreshManagedMeshComponent(CreatedComponent);
    ManagedComponentsBySlot.Add(SlotName, CreatedComponent);
    return CreatedComponent;
}

void UPMXCharacterEquipmentComponent::SetDesiredWeaponMesh(USkeletalMesh* InWeaponMesh)
{
    DesiredWeaponMesh = InWeaponMesh;
    const int32 ExistingWeaponBindingIndex = FindSlotBindingIndex(WeaponSlotName);
    if (InWeaponMesh || ExistingWeaponBindingIndex != INDEX_NONE)
    {
        UpsertDesiredBinding(BuildWeaponBinding(InWeaponMesh));
    }
    else
    {
        MirrorLegacyWeaponState();
    }
}

void UPMXCharacterEquipmentComponent::SetDesiredItemForSlot(const FPMXEquipmentSlotBindingEntry& InBinding)
{
    UpsertDesiredBinding(InBinding);
}

void UPMXCharacterEquipmentComponent::SetDesiredSlotBindings(const TArray<FPMXEquipmentSlotBindingEntry>& InBindings)
{
    DesiredSlotBindings.Reset();
    SlotConflicts.Reset();
    for (const FPMXEquipmentSlotBindingEntry& Binding : InBindings)
    {
        UpsertDesiredBinding(Binding);
    }
    MirrorLegacyWeaponState();
}

TArray<FPMXEquipmentSlotBindingEntry> UPMXCharacterEquipmentComponent::GetDesiredSlotBindings() const
{
    return DesiredSlotBindings;
}

void UPMXCharacterEquipmentComponent::UpsertDesiredBinding(const FPMXEquipmentSlotBindingEntry& InBinding)
{
    FPMXEquipmentSlotBindingEntry NormalizedBinding = InBinding;
    NormalizedBinding.SlotName = NormalizeSlotName(NormalizedBinding.SlotName);
    NormalizedBinding.ItemKind = NormalizeItemKind(NormalizedBinding.ItemKind, NormalizedBinding);
    if (NormalizedBinding.AttachSocketName.IsNone())
    {
        NormalizedBinding.AttachSocketName = (NormalizedBinding.SlotName == WeaponSlotName) ? AttachSocketName : TEXT("WeaponSocket");
    }

    const int32 ExistingIndex = FindSlotBindingIndex(NormalizedBinding.SlotName);
    if (ExistingIndex != INDEX_NONE)
    {
        RecordSlotConflict(DesiredSlotBindings[ExistingIndex], NormalizedBinding);
        DesiredSlotBindings.RemoveAt(ExistingIndex);
    }
    DesiredSlotBindings.Add(NormalizedBinding);
    MirrorLegacyWeaponState();
}

USkeletalMesh* UPMXCharacterEquipmentComponent::GetDesiredWeaponMesh() const
{
    return DesiredWeaponMesh;
}

void UPMXCharacterEquipmentComponent::SetAttachSocketName(FName InAttachSocketName)
{
    AttachSocketName = InAttachSocketName.IsNone() ? TEXT("WeaponSocket") : InAttachSocketName;

    const int32 WeaponBindingIndex = FindSlotBindingIndex(WeaponSlotName);
    if (WeaponBindingIndex != INDEX_NONE)
    {
        DesiredSlotBindings[WeaponBindingIndex].AttachSocketName = AttachSocketName;
    }
    else if (DesiredWeaponMesh)
    {
        UpsertDesiredBinding(BuildWeaponBinding(DesiredWeaponMesh));
    }

    if (GetManagedWeaponMeshComponent())
    {
        ApplyWeaponMeshToOwner();
    }
}

FName UPMXCharacterEquipmentComponent::GetAttachSocketName() const
{
    return AttachSocketName;
}

USceneComponent* UPMXCharacterEquipmentComponent::ApplyItemForSlot(FName SlotName)
{
    const int32 BindingIndex = FindSlotBindingIndex(SlotName);
    if (BindingIndex == INDEX_NONE)
    {
        return nullptr;
    }

    const FPMXEquipmentSlotBindingEntry& Binding = DesiredSlotBindings[BindingIndex];
    const FString NormalizedItemKind = NormalizeItemKind(Binding.ItemKind, Binding);
    FPMXEquipmentSlotAttachState& AttachState = UpsertSlotAttachState(Binding.SlotName);
    AttachState.SlotName = NormalizeSlotName(Binding.SlotName);
    AttachState.ItemPackageId = Binding.ItemPackageId;
    AttachState.ItemKind = NormalizedItemKind;
    AttachState.RequestedAttachSocketName = Binding.AttachSocketName;
    AttachState.ManagedComponentName.Reset();
    AttachState.ManagedComponentClass.Reset();
    AttachState.ManagedComponentAssetPath.Reset();

    USceneComponent* MeshComponent = EnsureManagedComponentForSlot(Binding, NormalizedItemKind);
    if (!MeshComponent)
    {
        AttachState.AttachResolutionMode = TEXT("managed_component_missing");
        MirrorLegacyWeaponState();
        return nullptr;
    }

    if (USkeletalMeshComponent* OwnerMesh = FindOwnerMeshComponent())
    {
    const FName TargetAttachName = ResolveAttachSocketName(OwnerMesh, Binding.SlotName, Binding.AttachSocketName, &AttachState);
        MeshComponent->AttachToComponent(
            OwnerMesh,
            FAttachmentTransformRules::SnapToTargetNotIncludingScale,
            TargetAttachName
        );
    }
    else
    {
        AttachState.AttachResolutionMode = TEXT("owner_mesh_missing");
    }

    if (IsStaticMeshKind(NormalizedItemKind))
    {
        if (UStaticMeshComponent* StaticMeshComponent = Cast<UStaticMeshComponent>(MeshComponent))
        {
            StaticMeshComponent->SetStaticMesh(Binding.StaticMesh);
        }
    }
    else
    {
        if (USkeletalMeshComponent* SkeletalMeshComponent = Cast<USkeletalMeshComponent>(MeshComponent))
        {
            SkeletalMeshComponent->SetSkeletalMesh(Binding.SkeletalMesh);
        }
    }

    RefreshManagedMeshComponent(MeshComponent);
    AttachState.ManagedComponentName = MeshComponent->GetName();
    AttachState.ManagedComponentClass = MeshComponent->GetClass()->GetName();
    AttachState.ManagedComponentAssetPath = ComponentAssetPath(MeshComponent);
    ManagedComponentsBySlot.Add(AttachState.SlotName, MeshComponent);
    MirrorLegacyWeaponState();
    return MeshComponent;
}

void UPMXCharacterEquipmentComponent::ApplySlotBindings()
{
    if (DesiredSlotBindings.Num() == 0 && DesiredWeaponMesh)
    {
        UpsertDesiredBinding(BuildWeaponBinding(DesiredWeaponMesh));
    }

    for (const FPMXEquipmentSlotBindingEntry& Binding : DesiredSlotBindings)
    {
        ApplyItemForSlot(Binding.SlotName);
    }
}

USkeletalMeshComponent* UPMXCharacterEquipmentComponent::ApplyWeaponMeshToOwner()
{
    return Cast<USkeletalMeshComponent>(ApplyItemForSlot(WeaponSlotName));
}

USceneComponent* UPMXCharacterEquipmentComponent::GetManagedComponentForSlot(FName SlotName) const
{
    const FName NormalizedSlotName = NormalizeSlotName(SlotName);
    if (const TObjectPtr<USceneComponent>* ExistingEntry = ManagedComponentsBySlot.Find(NormalizedSlotName))
    {
        return ExistingEntry->Get();
    }

    const int32 BindingIndex = FindSlotBindingIndex(NormalizedSlotName);
    if (BindingIndex == INDEX_NONE)
    {
        return nullptr;
    }

    const FPMXEquipmentSlotBindingEntry& Binding = DesiredSlotBindings[BindingIndex];
    return FindExistingManagedComponent(NormalizedSlotName, NormalizeItemKind(Binding.ItemKind, Binding));
}

USkeletalMeshComponent* UPMXCharacterEquipmentComponent::GetManagedWeaponMeshComponent() const
{
    return Cast<USkeletalMeshComponent>(GetManagedComponentForSlot(WeaponSlotName));
}

TArray<FPMXEquipmentSlotConflictEntry> UPMXCharacterEquipmentComponent::GetSlotConflicts() const
{
    return SlotConflicts;
}

TArray<FPMXEquipmentSlotAttachState> UPMXCharacterEquipmentComponent::GetResolvedSlotAttachStates() const
{
    return SlotAttachStates;
}

FName UPMXCharacterEquipmentComponent::GetResolvedAttachSocketName() const
{
    if (const FPMXEquipmentSlotAttachState* WeaponAttachState = FindSlotAttachState(WeaponSlotName))
    {
        return WeaponAttachState->ResolvedAttachSocketName;
    }
    return ResolvedAttachSocketName;
}

bool UPMXCharacterEquipmentComponent::HasResolvedAttachSocket() const
{
    if (const FPMXEquipmentSlotAttachState* WeaponAttachState = FindSlotAttachState(WeaponSlotName))
    {
        return WeaponAttachState->bResolvedAttachSocketExists;
    }
    return bResolvedAttachSocketExists;
}

FString UPMXCharacterEquipmentComponent::GetAttachResolutionMode() const
{
    if (const FPMXEquipmentSlotAttachState* WeaponAttachState = FindSlotAttachState(WeaponSlotName))
    {
        return WeaponAttachState->AttachResolutionMode;
    }
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

FName UPMXCharacterEquipmentComponent::ResolveAttachSocketName(
    USkeletalMeshComponent* OwnerMesh,
    FName SlotName,
    FName RequestedSocketName,
    FPMXEquipmentSlotAttachState* AttachState
)
{
    if (AttachState)
    {
        AttachState->ResolvedAttachSocketName = NAME_None;
        AttachState->bResolvedAttachSocketExists = false;
        AttachState->AttachResolutionMode = TEXT("owner_origin");
    }

    if (!OwnerMesh)
    {
        if (AttachState)
        {
            AttachState->AttachResolutionMode = TEXT("owner_mesh_missing");
        }
        return NAME_None;
    }

    const TArray<FName> Candidates = BuildAttachCandidates(RequestedSocketName, SlotName);
    for (const FName& Candidate : Candidates)
    {
        if (!Candidate.IsNone() && OwnerMesh->DoesSocketExist(Candidate))
        {
            if (AttachState)
            {
                AttachState->ResolvedAttachSocketName = Candidate;
                AttachState->bResolvedAttachSocketExists = true;
                AttachState->AttachResolutionMode = Candidate == RequestedSocketName ? TEXT("requested_socket") : TEXT("fallback_socket");
            }
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
            if (MatchesAttachPattern(BoneNameString, SlotName, RequestedSocketName))
            {
                if (AttachState)
                {
                    AttachState->ResolvedAttachSocketName = BoneName;
                    AttachState->bResolvedAttachSocketExists = true;
                    AttachState->AttachResolutionMode = TEXT("fallback_bone_pattern");
                }
                return BoneName;
            }

            const int32 BoneScore = ScoreFallbackBoneName(BoneNameString, SlotName, RequestedSocketName);
            if (BoneScore >= BestBoneScore)
            {
                BestBoneScore = BoneScore;
                BestBoneName = BoneName;
            }
        }

        if (!BestBoneName.IsNone() && BestBoneScore > 0)
        {
            if (AttachState)
            {
                AttachState->ResolvedAttachSocketName = BestBoneName;
                AttachState->bResolvedAttachSocketExists = true;
                AttachState->AttachResolutionMode = TEXT("fallback_bone_score");
            }
            return BestBoneName;
        }
    }

    return NAME_None;
}

void UPMXCharacterEquipmentComponent::RefreshManagedMeshComponent(USceneComponent* MeshComponent) const
{
    if (!MeshComponent)
    {
        return;
    }

    if (UPrimitiveComponent* PrimitiveComponent = Cast<UPrimitiveComponent>(MeshComponent))
    {
        PrimitiveComponent->SetVisibility(true, true);
        PrimitiveComponent->SetHiddenInGame(false, true);
        PrimitiveComponent->SetCastShadow(true);
        PrimitiveComponent->SetCollisionEnabled(ECollisionEnabled::NoCollision);
        PrimitiveComponent->MarkRenderTransformDirty();
        PrimitiveComponent->MarkRenderStateDirty();
    }

    MeshComponent->SetRelativeLocationAndRotation(FVector::ZeroVector, FRotator::ZeroRotator);

    if (USkeletalMeshComponent* SkeletalMeshComponent = Cast<USkeletalMeshComponent>(MeshComponent))
    {
        SkeletalMeshComponent->RefreshBoneTransforms();
        SkeletalMeshComponent->UpdateBounds();
        SkeletalMeshComponent->MarkRenderDynamicDataDirty();
    }
    else if (UStaticMeshComponent* StaticMeshComponent = Cast<UStaticMeshComponent>(MeshComponent))
    {
        StaticMeshComponent->UpdateBounds();
    }
}
